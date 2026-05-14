"""One-time migration: upload local jsonl files into Supabase.

- results.jsonl -> plates table (one row per distinct plate, with last seen date)
- enriched.jsonl -> tows table (one row per distinct tow event)

Uses the service_role key so writes bypass RLS. Idempotent — uses upsert.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from supabase import create_client

BOSTON_TZ = ZoneInfo("America/New_York")

ROOT = Path(__file__).parent

# Load .env into os.environ (tiny inline parser to avoid an extra dependency).
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(URL, KEY)

BATCH = 500


def parse_partial_date(s):
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except (ValueError, TypeError):
        return None


def parse_detail_time(s):
    """Boston website prints wall-clock ET. Localize so the UTC stored in
    Postgres is the real moment in time."""
    try:
        naive = datetime.strptime(s, "%m/%d/%Y %I:%M:%S %p")
        return naive.replace(tzinfo=BOSTON_TZ)
    except (ValueError, TypeError):
        return None


def migrate_plates():
    """results.jsonl -> plates table, keyed by (state, plate), latest date."""
    by_key = {}
    for line in (ROOT / "results.jsonl").open():
        r = json.loads(line)
        d = parse_partial_date(r.get("date", ""))
        if d is None:
            continue
        key = (r.get("state", ""), r.get("plate", ""))
        if key not in by_key or d > by_key[key]:
            by_key[key] = d

    rows = [
        {"state": s, "plate": p, "last_seen_date": d.isoformat()}
        for (s, p), d in by_key.items()
        if p  # skip empty plates
    ]
    print(f"Plates: {len(rows)} rows to upsert")

    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        client.table("plates").upsert(batch, on_conflict="state,plate").execute()
        print(f"  {min(i + BATCH, len(rows))}/{len(rows)}")
    print("Plates done.")


def migrate_tows():
    """enriched.jsonl -> tows table, deduped by (state, plate, time)."""
    by_key = {}
    for line in (ROOT / "enriched.jsonl").open():
        r = json.loads(line)
        dt = parse_detail_time(r.get("Time", ""))
        if dt is None or not r.get("Plate"):
            continue
        mod = parse_detail_time(r.get("Modified", ""))
        key = (r.get("State", ""), r.get("Plate", ""), dt.isoformat())
        by_key[key] = {
            "state":        r.get("State", "") or "",
            "plate":        r.get("Plate", ""),
            "time":         dt.isoformat(),
            "year":         r.get("Year", "") or "",
            "make":         r.get("Make", "") or "",
            "model":        r.get("Model", "") or "",
            "color":        r.get("Color", "") or "",
            "vehicle_desc": r.get("Desc", "") or "",
            "tow_company":  r.get("By", "") or "",
            "agency":       r.get("Agency", "") or "",
            "reason":       r.get("Reason", "") or "",
            "modified":     mod.isoformat() if mod else None,
        }

    rows = list(by_key.values())
    print(f"Tows: {len(rows)} unique tow events to upsert")

    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        client.table("tows").upsert(batch, on_conflict="state,plate,time").execute()
        print(f"  {min(i + BATCH, len(rows))}/{len(rows)}")
    print("Tows done.")


if __name__ == "__main__":
    migrate_plates()
    migrate_tows()
    print("Migration complete.")
