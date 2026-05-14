"""Build data.json / data.js from enriched.jsonl.

Reads every enriched tow event, dedupes (state, plate, time), filters to
the last 7 days, and writes data.json + data.js for the static website.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
ENRICHED_PATH = ROOT / "enriched.jsonl"
JSON_PATH = ROOT / "data.json"
JS_PATH = ROOT / "data.js"
WINDOW_DAYS = 7


def parse_time(s):
    """Parse '5/12/2026 10:47:16 PM' → datetime, or None."""
    try:
        return datetime.strptime(s, "%m/%d/%Y %I:%M:%S %p")
    except (ValueError, TypeError):
        return None


def main():
    today = date.today()
    cutoff_date = today - timedelta(days=WINDOW_DAYS - 1)
    cutoff = datetime.combine(cutoff_date, datetime.min.time())

    by_key = {}
    total = 0
    if ENRICHED_PATH.exists():
        for line in ENRICHED_PATH.open():
            row = json.loads(line)
            dt = parse_time(row.get("Time", ""))
            if dt is None or dt < cutoff:
                continue
            total += 1
            key = (row.get("State", ""), row.get("Plate", ""), dt.isoformat())
            # Same event appears multiple times across the detail page's tables;
            # last write wins (they should be identical anyway).
            by_key[key] = {
                "state": row.get("State", ""),
                "plate": row.get("Plate", ""),
                "year": row.get("Year", ""),
                "make": row.get("Make", ""),
                "model": row.get("Model", ""),
                "color": row.get("Color", ""),
                "desc": row.get("Desc", ""),
                "by": row.get("By", ""),
                "agency": row.get("Agency", ""),
                "reason": row.get("Reason", ""),
                "time": dt.isoformat(timespec="seconds"),
            }

    records = sorted(by_key.values(), key=lambda r: r["time"], reverse=True)
    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window_start": cutoff_date.isoformat(),
        "window_end": today.isoformat(),
        "count": len(records),
        "records": records,
    }
    JSON_PATH.write_text(json.dumps(output, indent=2))
    JS_PATH.write_text("window.TOW_DATA = " + json.dumps(output) + ";\n")
    print(f"Wrote {len(records)} unique events (from {total} raw rows) "
          f"to {JSON_PATH.name} and {JS_PATH.name}")


if __name__ == "__main__":
    main()
