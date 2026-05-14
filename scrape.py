"""Resumable parallel scraper for Boston towed-car records.

Hits /towing/search/?plate=<trigram> for every 3-letter combo AAA..ZZZ,
parses the result table, and appends rows to results.jsonl. Progress is
tracked in progress.json so re-running picks up where it left off.

Uses N worker threads (default 4); each worker self-paces with REQUEST_DELAY
between its own requests, giving a total throughput of ~N requests/sec.

Failed prefixes (HTTP error / timeout) are NOT marked done, so they're
retried automatically on the next run.

Output row schema:
    {"prefix": "AAA", "state": "MA", "plate": "1ABC23",
     "make_model": "2024 BLK Sienna", "date": "4/20/2026"}
"""

import itertools
import json
import os
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cityofboston.gov/towing/search/"
HEADERS = {"User-Agent": "find-my-towed-car-boston (github.com/hafsaah1)"}
REQUEST_DELAY = float(os.environ.get("SCRAPE_DELAY", "1.0"))  # per-worker delay
TIMEOUT = 15
WORKERS = int(os.environ.get("SCRAPE_WORKERS", "4"))

ROOT = Path(__file__).parent
RESULTS_PATH = ROOT / "results.jsonl"
PROGRESS_PATH = ROOT / "progress.json"

write_lock = threading.Lock()
progress_lock = threading.Lock()


def all_trigrams():
    for a, b, c in itertools.product(string.ascii_uppercase, repeat=3):
        yield a + b + c


def load_progress():
    if PROGRESS_PATH.exists():
        return json.loads(PROGRESS_PATH.read_text())
    return {"done": []}


def save_progress(progress):
    PROGRESS_PATH.write_text(json.dumps(progress))


def parse_results(html, prefix):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tblplates")
    if not table:
        return
    for row in table.select("tr"):
        cells = row.select("td")
        if len(cells) != 3:
            continue
        plate_cell = cells[0].get_text(" ", strip=True)
        parts = plate_cell.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 2 and parts[0].isalpha():
            state, plate = parts[0], parts[1]
        else:
            state, plate = "", plate_cell
        yield {
            "prefix": prefix,
            "state": state,
            "plate": plate,
            "make_model": cells[1].get_text(" ", strip=True),
            "date": cells[2].get_text(" ", strip=True),
        }


class Worker:
    def __init__(self, name, results_file, progress, done, stats):
        self.name = name
        self.session = requests.Session()
        self.results_file = results_file
        self.progress = progress
        self.done = done
        self.stats = stats

    def fetch(self, prefix):
        r = self.session.get(BASE_URL, params={"plate": prefix},
                             headers=HEADERS, timeout=TIMEOUT)
        return r.status_code, r.text

    def run(self, prefix):
        try:
            status, html = self.fetch(prefix)
        except requests.RequestException as e:
            with progress_lock:
                self.stats["errors"] += 1
            print(f"[{self.name} {prefix}] network error: {e}", flush=True)
            time.sleep(REQUEST_DELAY * 3)
            return

        if status != 200:
            with progress_lock:
                self.stats["errors"] += 1
            print(f"[{self.name} {prefix}] HTTP {status} — will retry next run",
                  flush=True)
            time.sleep(REQUEST_DELAY * 3)
            return

        rows = list(parse_results(html, prefix))
        with write_lock:
            for row in rows:
                self.results_file.write(json.dumps(row) + "\n")

        with progress_lock:
            self.stats["completed"] += 1
            self.stats["total_rows"] += len(rows)
            self.done.add(prefix)
            n = self.stats["completed"]
            if n % 25 == 0 or rows:
                elapsed = time.time() - self.stats["started"]
                rate = n / elapsed if elapsed else 0
                remaining = self.stats["total"] - n
                eta = remaining / rate if rate else 0
                print(f"[{n}/{self.stats['total']}] {prefix} -> {len(rows)} rows "
                      f"(rate {rate:.2f} q/s, eta {eta/60:.1f} min, "
                      f"errors {self.stats['errors']})", flush=True)
            if n % 100 == 0:
                self.results_file.flush()
                self.progress["done"] = sorted(self.done)
                save_progress(self.progress)

        time.sleep(REQUEST_DELAY)


def main(workers=WORKERS, limit=None):
    progress = load_progress()
    done = set(progress["done"])
    queue = [q for q in all_trigrams() if q not in done]
    if limit:
        queue = queue[:limit]
    total = len(queue)
    print(f"Resuming with {len(done)} done, {total} remaining, {workers} workers",
          flush=True)

    results_file = RESULTS_PATH.open("a", encoding="utf-8")
    stats = {"completed": 0, "errors": 0, "total_rows": 0,
             "total": total, "started": time.time()}

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # Each worker owns its own session via a thread-local-ish pattern.
            worker_pool = [Worker(f"w{i+1}", results_file, progress, done, stats)
                           for i in range(workers)]
            # Round-robin assign work to workers via the pool.
            futures = []
            for i, prefix in enumerate(queue):
                w = worker_pool[i % workers]
                futures.append(pool.submit(w.run, prefix))
            for f in futures:
                f.result()
    finally:
        results_file.close()
        with progress_lock:
            progress["done"] = sorted(done)
            save_progress(progress)
        print(f"Stopped. {len(done)} prefixes done total, "
              f"{stats['errors']} errors this run, "
              f"{stats['total_rows']} new rows.", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    workers = WORKERS
    limit = None
    for a in args:
        if a.startswith("--workers="):
            workers = int(a.split("=", 1)[1])
        elif a.isdigit():
            limit = int(a)
    main(workers=workers, limit=limit)
