# Reel Routes — Film Festival Scouting

An interactive map app that helps filmmakers find festivals to submit to and plan
the trip: live flights, hotels (with distance-to-venue), car rentals, and
rideshare deep-links, all filtered by budget, genre, runtime, radius, and dates.

- **Backend:** Python + FastAPI, SQLite (SQLAlchemy async), APScheduler for nightly FilmFreeway sync.
- **Frontend:** vanilla JS + Leaflet (dark cinematic map). No build step.
- **Geocoding:** OpenStreetMap Nominatim (free, no key needed) — ZIP or City, State autocomplete.
- **Flights:** [Serpapi](https://serpapi.com/) for structured Google Flights data (100 free searches/month).

---

## Quick start

### Windows (one command)

```bat
start.bat
```

`start.bat` creates a venv, installs all dependencies, copies `backend/.env.example → backend/.env`, and starts the server.

### macOS / Linux

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit NOMINATIM_EMAIL
uvicorn app.main:app --reload
```

Backend runs at **http://127.0.0.1:8000** — FastAPI serves the frontend too, so you only run one process.

Interactive API docs: **http://127.0.0.1:8000/docs**

### (Optional) Frontend on its own dev server

Open `frontend/` with the VSCode **Live Server** extension (port 5500). `js/api.js` auto-points to the backend on :8000.

---

## Configuration (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and set:

| Variable | Required | Description |
|---|---|---|
| `NOMINATIM_EMAIL` | Yes | Your e-mail — OSM usage policy requires a contact |
| `SERPAPI_KEY` | No | Enables live Google Flights ([get one at serpapi.com](https://serpapi.com/)) |
| `ENABLE_LIVE_SCRAPING` | No | `True` to enable Playwright scrapers for hotels/cars |

Everything works in **ESTIMATE** mode with no API keys. Live data badges appear per-source as each key is configured and scrapes succeed.

---

## Running tests

```bash
cd backend
python -m pytest tests/ -v
```

- `tests/test_unit.py` — `haversine_mi`, `rideshare_estimates`, fit-score math
- `tests/test_contract.py` — every `/api/*` route verified for correct response shape

---

## How live scraping works

1. Set `ENABLE_LIVE_SCRAPING=True` in `backend/.env`
2. Run `playwright install chromium`
3. Restart the backend

The UI shows `ESTIMATE` or `LIVE` badges per data source. If a scrape fails, it silently falls back to an estimate — the app never breaks.

> **Note:** Metasearch site DOMs change often. The selectors in `app/scrapers/hotels.py` are starting points and may need tuning. Respect each site's Terms of Service and `robots.txt`.

---

## Architecture

```
backend/
  app/
    main.py            FastAPI app, all routes, serves the frontend
    config.py          env-driven settings (pydantic-settings)
    models.py          shared response shapes
    geocode.py         Nominatim ZIP / City,State autocomplete
    db.py              SQLAlchemy async setup + FestivalRow model
    scheduler.py       APScheduler — nightly FilmFreeway field refresh
    data/festivals.json  seed data loaded into SQLite on first run
    scrapers/
      base.py          cache, geo math, Playwright helper
      filmfreeway.py   refresh deadlines/fees from FilmFreeway pages
      flights.py       Serpapi (Google Flights) + estimate fallback
      hotels.py        Booking.com scrape + estimate, venue-radius filter
      transport.py     car rentals + Uber/Lyft deep-links & estimates
  tests/
    test_unit.py       unit tests (haversine, rideshare, fit score)
    test_contract.py   contract tests (every /api/* route shape)
frontend/
  index.html           app shell
  css/styles.css       cinematic dark theme
  js/api.js            backend client (single place for the base URL)
  js/app.js            map, autocomplete, search, detail panel
```

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, live-scraping flag, festival counts |
| GET | `/api/geocode?q=` | ZIP / City,State suggestions (min 3 chars) |
| GET | `/api/festivals?lat=&lng=&...` | ranked festival matches with fit score |
| GET | `/api/festivals/{id}/refresh` | live FilmFreeway refresh for one festival |
| GET | `/api/flights?origin=&fid=&date=` | flight offers + booking link |
| GET | `/api/hotels?fid=&radius_mi=&...` | hotels within radius of venue |
| GET | `/api/cars?fid=` | car rental options |
| GET | `/api/rideshare?plat=&plng=&fid=` | Uber/Lyft estimate + deep-links |
| GET | `/api/admin/festivals` | list all festivals (including pending/inactive) |
| POST | `/api/admin/festivals` | add a new festival (status: pending_review) |
| POST | `/api/admin/festivals/{id}/approve` | mark festival active |
| POST | `/api/admin/festivals/{id}/deactivate` | mark festival inactive |
| POST | `/api/admin/festivals/{id}/reactivate` | restore inactive festival |
| POST | `/api/admin/sync` | trigger festival catalog sync |
| POST | `/api/admin/field-refresh` | trigger FilmFreeway field refresh |

---

## URL sharing

After a search, the URL hash encodes your origin, dates, genres, and filters — paste the URL to share or bookmark an exact search. No account needed.
