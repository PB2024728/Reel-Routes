# Reel Routes — Film Festival Scouting

An interactive map app that helps filmmakers find festivals to submit to and plan
the trip: live flights, hotels (with distance-to-venue), car rentals, and
rideshare deep-links, all filtered by budget, genre, runtime, radius, and dates.

- **Backend:** Python + FastAPI, with self-hosted Playwright scrapers (open source, free).
- **Frontend:** vanilla JS + Leaflet (dark cinematic map).
- **Geocoding:** OpenStreetMap Nominatim (free, no key) — ZIP or City, State autocomplete.

---

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # only needed when you turn on live scraping
cp .env.example .env                 # then edit NOMINATIM_EMAIL
uvicorn app.main:app --reload
```

Backend now runs at **http://127.0.0.1:8000**
- App UI: http://127.0.0.1:8000/
- Interactive API docs: http://127.0.0.1:8000/docs

That's it — FastAPI serves the frontend too, so you only run one process.

### 2. (Optional) Frontend on its own dev server
If you prefer hot-reload on the frontend, open `frontend/` with the VSCode
**Live Server** extension (port 5500). `api.js` auto-points to the backend on :8000.

---

## How "live" works

Everything works immediately in **ESTIMATE** mode (distance-based costs + real
booking links). To switch on real scraped prices:

1. In `.env`, set `ENABLE_LIVE_SCRAPING=True`.
2. Run `playwright install chromium` if you haven't.
3. Restart the backend.

The badges in the UI flip from `ESTIMATE` to `LIVE` per data source as scrapes
succeed. If a scrape fails, that source silently falls back to an estimate — the
app never breaks.

> **Scraper selectors need tuning.** The Playwright selectors in
> `app/scrapers/flights.py` and `hotels.py` are starting points; metasearch sites
> change their DOM often. For flights, the most stable path is the official
> **Amadeus** API — drop your credentials in `.env` and implement the `TODO` in
> `flights.py`. Always respect each site's Terms of Service and robots.txt, and
> keep the cache TTL high (default 6h) to stay polite.

---

## Architecture

```
backend/
  app/
    main.py            FastAPI app + all routes; also serves the frontend
    config.py          env-driven settings (pydantic-settings)
    models.py          shared response shapes
    geocode.py         Nominatim ZIP / City,State autocomplete
    data/festivals.json  seed festival DB (swap for live source / CSV)
    scrapers/
      base.py          cache, geo math, Playwright helper
      filmfreeway.py   refresh deadlines/fees from FilmFreeway pages
      flights.py       Google Flights scrape + Amadeus slot + estimate
      hotels.py        Booking.com scrape + estimate, venue-radius filter
      transport.py     car rentals + Uber/Lyft deep-links & estimates
frontend/
  index.html           app shell
  css/styles.css       cinematic dark theme
  js/api.js            backend client (one place for the base URL)
  js/app.js            map, autocomplete, search, detail panel
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status + whether live scraping is on |
| GET | `/api/geocode?q=` | ZIP / City,State suggestions |
| GET | `/api/festivals?lat=&lng=&...` | ranked festival matches |
| GET | `/api/festivals/{id}/refresh` | live FilmFreeway refresh |
| GET | `/api/flights?origin=&fid=&date=` | flight offers + booking link |
| GET | `/api/hotels?fid=&radius_mi=&...` | hotels within radius of venue |
| GET | `/api/cars?fid=` | car rental options |
| GET | `/api/rideshare?plat=&plng=&fid=` | Uber/Lyft estimate + deep-links |

---

## Roadmap / good next steps for Claude Code

- Replace `festivals.json` with a live FilmFreeway crawler or a maintained CSV.
- Implement the Amadeus path in `flights.py` for reliable fares.
- Persist the cache in Redis or SQLite instead of in-memory.
- Add real festival messaging (FilmFreeway has no public API — likely email relay).
- Add user accounts + saved festival lists.

See `CLAUDE.md` for working notes geared to the Claude Code extension.
