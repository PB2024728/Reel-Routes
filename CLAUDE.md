# CLAUDE.md — project notes for Claude Code

## What this is
Reel Routes: a festival-scouting map app for filmmakers. FastAPI backend +
vanilla JS/Leaflet frontend. Travel data (flights/hotels/cars) comes from
Playwright scrapers with estimate fallbacks; rideshare is deep-links + estimates.

## Conventions
- Backend is Python 3.11+, FastAPI, async. Keep endpoints thin; logic lives in
  `app/scrapers/*` and `app/geocode.py`.
- Every scraper returns `(rows, is_live)` and must **never raise** to the caller —
  catch and fall back to an estimate so the app stays up.
- Frontend has no build step. `js/api.js` is the only place that knows the backend
  URL. `js/app.js` exposes a single `UI` object; HTML calls `UI.method()`.
- Don't put secrets in code. Everything tunable is in `.env` (see `.env.example`).

## Where to make common changes
- Add/modify festivals → `app/data/festivals.json` (matches `models.Festival`).
- Tune a scraper's selectors → the `_scrape_*` functions in `app/scrapers/`.
- Add an official API (e.g. Amadeus) → implement the `TODO` in `flights.py`;
  creds already wired through `config.py`.
- Change the fit-score formula → `search_festivals()` in `app/main.py`.

## Running
```bash
cd backend && uvicorn app.main:app --reload   # serves API + UI on :8000
```
Live scraping is OFF by default. Flip `ENABLE_LIVE_SCRAPING=True` in `.env` and
run `playwright install chromium` to enable it.

## Known sharp edges
- Metasearch DOMs (Google Flights, Booking.com) change often; expect selector
  maintenance. Amadeus is the stable alternative for flights.
- Nominatim has a rate-limit usage policy; cache is on by default. For scale,
  self-host Nominatim or use a paid geocoder.
- Uber/Lyft have no public fare API; estimates are transparent and labeled.
  Respect each site's ToS/robots.txt before scraping at volume.

## Tests to add (none yet)
- Unit-test `haversine_mi`, `rideshare_estimates`, and the fit-score math.
- A contract test that every `/api/*` route returns the documented shape.
