"""Enrich recently-seen plates with full tow-event data, writing to Supabase.

Reads plates with `last_seen_date` in the last 7 days from the `plates` table,
fetches each plate's detail page from cityofboston.gov, parses every tow
event listed there, and upserts into the `tows` table.

Uses N worker threads (default 4) — each self-paced at REQUEST_DELAY sec.

Credentials via environment (works for both .env locally and CI secrets):
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from supabase import create_client

BASE_URL = "https://www.cityofboston.gov/towing/search/"
HEADERS = {"User-Agent": "find-my-towed-car-boston (github.com/hafsaah1)"}
REQUEST_DELAY = 1.0
TIMEOUT = 15
WINDOW_DAYS = 7
WORKERS = int(os.environ.get("ENRICH_WORKERS", "4"))
TIME_BUDGET_SEC = int(os.environ.get("ENRICH_BUDGET_SEC", "300"))
BOSTON_TZ = ZoneInfo("America/New_York")

DETAIL_KEYS = {"State", "Plate", "Year", "Make", "Model", "Desc",
               "Color", "By", "Agency", "Reason", "Time", "Modified"}

ROOT = Path(__file__).parent
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

acc = {}                  # key -> row dict, deduped accumulator
acc_lock = threading.Lock()
stats = {"done": 0, "errors": 0, "started": 0}
stats_lock = threading.Lock()


def parse_detail_time(s):
    try:
        return datetime.strptime(s, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=BOSTON_TZ)
    except (ValueError, TypeError):
        return None


def parse_detail_tables(html):
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table"):
        rec = {}
        for row in table.select("tr"):
            th = row.select_one("th"); td = row.select_one("td")
            if not (th and td):
                continue
            key = th.get_text(strip=True)
            if key in DETAIL_KEYS:
                rec[key] = td.get_text(" ", strip=True)
        if {"State", "Plate", "Time"}.issubset(rec):
            yield rec


def to_row(rec):
    t = parse_detail_time(rec.get("Time", ""))
    if t is None or not rec.get("Plate"):
        return None
    m = parse_detail_time(rec.get("Modified", ""))
    return {
        "state":        rec.get("State", "") or "",
        "plate":        rec.get("Plate", ""),
        "time":         t.isoformat(),
        "year":         rec.get("Year", "") or "",
        "make":         rec.get("Make", "") or "",
        "model":        rec.get("Model", "") or "",
        "color":        rec.get("Color", "") or "",
        "vehicle_desc": rec.get("Desc", "") or "",
        "tow_company":  rec.get("By", "") or "",
        "agency":       rec.get("Agency", "") or "",
        "reason":       rec.get("Reason", "") or "",
        "modified":     m.isoformat() if m else None,
    }


def fetch_one(session, plate, deadline):
    if time.time() > deadline:
        return
    try:
        r = session.get(BASE_URL, params={"plate": plate},
                        headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        with stats_lock: stats["errors"] += 1
        time.sleep(REQUEST_DELAY * 2)
        return
    if r.status_code != 200:
        with stats_lock: stats["errors"] += 1
        time.sleep(REQUEST_DELAY * 2)
        return
    rows = [to_row(rec) for rec in parse_detail_tables(r.text)]
    rows = [row for row in rows if row]
    with acc_lock:
        for row in rows:
            acc[(row["state"], row["plate"], row["time"])] = row
    with stats_lock:
        stats["done"] += 1
    time.sleep(REQUEST_DELAY)


def main():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    cutoff = (date.today() - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    plates = []
    offset = 0
    while True:
        r = (client.table("plates")
             .select("state,plate")
             .gte("last_seen_date", cutoff)
             .order("last_seen_date", desc=True)
             .range(offset, offset + 999)
             .execute())
        plates.extend(r.data)
        if len(r.data) < 1000: break
        offset += 1000
    print(f"Enriching {len(plates)} recent plates with {WORKERS} workers, "
          f"{TIME_BUDGET_SEC}s budget", flush=True)

    stats["started"] = time.time()
    deadline = stats["started"] + TIME_BUDGET_SEC

    def worker_task(plate):
        # one session per submission — cheap, threadsafe
        s = requests.Session()
        fetch_one(s, plate, deadline)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(worker_task, p["plate"]) for p in plates]
        for f in futures:
            try: f.result()
            except Exception as e:
                print(f"worker error: {e}", flush=True)

    # Final upsert
    rows = list(acc.values())
    print(f"Upserting {len(rows)} unique tow events…", flush=True)
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        client.table("tows").upsert(rows[i:i+BATCH],
            on_conflict="state,plate,time").execute()
    print(f"Done. {stats['done']} plates fetched, {stats['errors']} errors, "
          f"{len(rows)} tow events written.", flush=True)


if __name__ == "__main__":
    main()
