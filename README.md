# find-my-towed-car-boston

A live map of every car towed in Boston in the last 7 days, styled after
[rodinrooh.com](https://www.rodinrooh.com) (SF) but for Boston data.

## How it works

The City of Boston exposes a tow lookup at
[cityofboston.gov/towing/search/](https://www.cityofboston.gov/towing/search/),
but only lets you search **one plate at a time** — no public list endpoint.

The trick: the search accepts as little as 3 characters and treats them as
a *contains* match. So this project enumerates every 3-letter combination
from `AAA` to `ZZZ` (17,576 queries), parses each result table, and stitches
the matches together. Then it follows up with one detail-page request per
recent plate to grab full timestamps, reasons, and towing-company info.

## Architecture

```
   GitHub Actions cron  ──► enrich.py ──► Supabase Postgres
                                                │
                                                ▼
                                  Vercel static site (index.html)
```

- **Initial scrape** (`scrape.py`) discovers plates that have ever been towed.
  Runs locally — ~2 hrs for full alphabet coverage at 4 workers.
- **Migration** (`migrate_to_supabase.py`) uploads the local jsonl files to
  Supabase tables `plates` and `tows`.
- **Enrich** (`enrich.py`) — runs every 30 min in GitHub Actions. Fetches
  detail pages for plates seen in the last 7 days, upserts new tow events
  into `tows`.
- **Frontend** (`index.html`) — static site on Vercel. Fetches from the
  Supabase REST API on page load via the public anon key.

## Files

| File | Role |
|---|---|
| `scrape.py` | Resumable parallel trigram scraper. Writes `results.jsonl`. |
| `migrate_to_supabase.py` | One-time upload of local data to Supabase. |
| `enrich.py` | Cron-driven re-enrichment of recent plates into Supabase. |
| `supabase_schema.sql` | Tables, indexes, RLS policies. |
| `geo.js` | Tow-company → coordinates / impound address lookup. |
| `config.js` | Public Supabase URL + anon key. |
| `index.html` | The website. |
| `.github/workflows/refresh.yml` | 30-min cron. |

## Run from scratch

1. `pip install requests beautifulsoup4 supabase`
2. Create a Supabase project, paste `supabase_schema.sql` into the SQL editor.
3. Copy `.env.example` → `.env` and fill in the keys.
4. `python scrape.py` (one-time, ~2 hrs)
5. `python migrate_to_supabase.py`
6. Add `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` to GitHub repo secrets.
7. Edit `config.js` with your project URL + anon key.
8. Deploy `index.html` + `geo.js` + `config.js` to any static host.

## Approximations

- **No per-car coordinates** in the source. Pins are placed near each
  towing company's yard with deterministic jitter.
- **BTD city-wide tows** (Boston's own street-cleaning) don't map to a
  single neighborhood; they're scattered across Boston by plate hash.
- The "previous month" note on Boston's own page is a lie — the source
  actually returns multiple years of history.

## Credits

Inspired by [rodinrooh.com](https://www.rodinrooh.com) and
[Riley Walz's SF parking map](https://walzr.com/sf-parking/).

## License

MIT.
