"""Enrich recent partial-match results with full detail-page data.

The partial-match table only gives plate/make-model/date. The exact-plate
detail page returns one record per tow event with State, Plate, Year, Make,
Model, Color, Desc, By (tow company), Agency, Reason, Time (full timestamp),
and Modified.

Strategy: collect every unique plate from results.jsonl whose listed date
falls within the last 7 days, fetch each plate's detail page once, parse
every tow record on the page, and append to enriched.jsonl.

Resumable via enrich_progress.json.
"""

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cityofboston.gov/towing/search/"
HEADERS = {"User-Agent": "find-my-towed-car-boston (github.com/hafsaah1)"}
REQUEST_DELAY = 1.0
TIMEOUT = 15
WINDOW_DAYS = 7

ROOT = Path(__file__).parent
RESULTS_PATH = ROOT / "results.jsonl"
ENRICHED_PATH = ROOT / "enriched.jsonl"
PROGRESS_PATH = ROOT / "enrich_progress.json"

DETAIL_KEYS = {"State", "Plate", "Year", "Make", "Model", "Desc",
               "Color", "By", "Agency", "Reason", "Time", "Modified"}


def parse_partial_date(s):
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except (ValueError, TypeError):
        return None


def collect_recent_plates():
    """Plates with any partial-match row dated within the last 7 days."""
    today = date.today()
    cutoff = today - timedelta(days=WINDOW_DAYS - 1)
    plates = {}  # (state, plate) -> latest_date seen
    for line in RESULTS_PATH.open():
        row = json.loads(line)
        d = parse_partial_date(row["date"])
        if d is None or d < cutoff or d > today:
            continue
        key = (row["state"], row["plate"])
        if key not in plates or d > plates[key]:
            plates[key] = d
    return plates


def parse_detail_tables(html):
    """Yield dicts, one per tow event found in the detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table"):
        record = {}
        for row in table.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not (th and td):
                continue
            key = th.get_text(strip=True)
            if key in DETAIL_KEYS:
                record[key] = td.get_text(" ", strip=True)
        # A real tow record has at least these three fields.
        if {"State", "Plate", "Time"}.issubset(record):
            yield record


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"done": []}


def save_progress(progress):
    PROGRESS_PATH.write_text(json.dumps(progress))


def main():
    plates = collect_recent_plates()
    print(f"Found {len(plates)} unique recent plates to enrich")

    progress = load_progress()
    done = {tuple(x) for x in progress["done"]}
    pending = [p for p in plates if p not in done]
    print(f"Already enriched: {len(done)}, pending: {len(pending)}")

    session = requests.Session()
    out = ENRICHED_PATH.open("a", encoding="utf-8")
    errors = 0
    started = time.time()

    try:
        for i, (state, plate) in enumerate(pending, 1):
            try:
                r = session.get(BASE_URL, params={"plate": plate},
                                headers=HEADERS, timeout=TIMEOUT)
            except requests.RequestException as e:
                errors += 1
                print(f"[{plate}] network error: {e}", flush=True)
                time.sleep(REQUEST_DELAY * 3)
                continue
            if r.status_code != 200:
                errors += 1
                print(f"[{plate}] HTTP {r.status_code}", flush=True)
                time.sleep(REQUEST_DELAY * 3)
                continue

            records = list(parse_detail_tables(r.text))
            for rec in records:
                out.write(json.dumps(rec) + "\n")
            done.add((state, plate))
            if i % 10 == 0 or records:
                elapsed = time.time() - started
                rate = i / elapsed if elapsed else 0
                eta = (len(pending) - i) / rate if rate else 0
                print(f"[{i}/{len(pending)}] {plate} -> {len(records)} events "
                      f"(rate {rate:.2f} q/s, eta {eta/60:.1f} min, errors {errors})",
                      flush=True)
            if i % 25 == 0:
                out.flush()
                progress["done"] = [list(k) for k in sorted(done)]
                save_progress(progress)
            time.sleep(REQUEST_DELAY)
    finally:
        out.close()
        progress["done"] = [list(k) for k in sorted(done)]
        save_progress(progress)
        print(f"Stopped. {len(done)} plates enriched total, {errors} errors this run.",
              flush=True)


if __name__ == "__main__":
    main()
