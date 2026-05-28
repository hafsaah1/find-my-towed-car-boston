# find-my-towed-car-boston

A live map of every car towed in Boston in the last 7 days


## How it works

The City of Boston exposes a tow lookup at
[cityofboston.gov/towing/search/](https://www.cityofboston.gov/towing/search/),
but only lets you search **one plate at a time** — no public list endpoint.



## Approximations

- **No per-car coordinates** in the source. Pins are placed near each
  towing company's yard with deterministic jitter.
- **BTD city-wide tows** (Boston's own street-cleaning) don't map to a
  single neighborhood; they're scattered across Boston by plate hash.
- The "previous month" note on Boston's own page is a lie — the source
  actually returns multiple years of history.

## Credits

Inspired by [Riley Walz's SF parking map](https://walzr.com/sf-parking/).

## License

MIT.
