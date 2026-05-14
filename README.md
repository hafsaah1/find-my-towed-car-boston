# find-my-towed-car-boston

A live-ish map of every car towed in Boston in the last 7 days, styled after
[rodinrooh.com](https://www.rodinrooh.com) (SF) but for Boston data.

![preview](https://placehold.co/800x400?text=Boston+Towed+Cars)

## How it works

The City of Boston exposes a tow lookup at
[cityofboston.gov/towing/search/](https://www.cityofboston.gov/towing/search/),
but only lets you search **one plate at a time** — no public list endpoint.

The trick: the search accepts as little as 3 characters and treats them as a
*contains* match. So this project enumerates every 3-letter combination from
`AAA` to `ZZZ` (17,576 queries), parses each result table, and stitches the
matches together. Then it follows up with one detail-page request per recent
plate to grab full timestamps, reasons, and towing-company info.

## Files

| File | Role |
|---|---|
| `scrape.py` | Resumable, parallel (4-worker) trigram scraper. Writes `results.jsonl`. |
| `enrich.py` | For each plate from the last 7 days, fetches the exact-plate detail page. Writes `enriched.jsonl`. |
| `build_json.py` | Dedupes the enriched events, filters to the last 7 days, writes `data.json` + `data.js`. |
| `refresh-loop.sh` | Background loop that re-runs enrich + build every 10 min. |
| `geo.js` | Tow-company → coordinates / impound address lookup (used by the map). |
| `index.html` | The website. Loads `geo.js` + `data.js`. |

## Run

```bash
pip install requests beautifulsoup4
python scrape.py        # ~1–2 hours for full coverage at 4 workers
python enrich.py        # ~5–10 min depending on how many recent plates
python build_json.py    # writes data.json / data.js
open index.html         # works from file:// — no server needed
```

Or, to keep it auto-updating:

```bash
./refresh-loop.sh &     # enrich + build every 10 min
```

## Approximations (be honest)

- **No per-car coordinates** in the source — only the towing company name.
  Pins are placed near each company's yard with deterministic jitter.
  Pin colors are per make so all Hondas look the same.
- **BTD city-wide tows** (Boston's own street-cleaning operation) don't map
  to any single neighborhood, so they're scattered deterministically across
  Boston by plate hash.
- The "previous month" note on Boston's own page is a lie — the source
  actually returns multiple years of history.

## Credits

Inspired by [rodinrooh.com](https://www.rodinrooh.com) and
[Riley Walz's SF parking map](https://walzr.com/sf-parking/).

## License

MIT.
