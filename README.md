# Reel Routes — Film Festival Scouting for Filmmakers

Reel Routes is an interactive map app that helps independent filmmakers discover
film festivals and plan the trip to attend them. Enter your city or ZIP code,
set your filters (genre, runtime, submission budget, date range), and get a
ranked list of matching festivals plotted on a live map — with flight estimates,
nearby hotels, car rentals, and rideshare deep-links for each one.

**Everything works out of the box with no API keys.** Prices default to
distance-based estimates. Add a free [Serpapi](https://serpapi.com/) key to
get real Google Flights data, and optionally enable Playwright scraping for
hotel and car prices.

---

## Features

- **Festival search** — filter by genre, runtime, submission fee cap, radius,
  and deadline date window; results are ranked by a fit score (genre match,
  deadline urgency, distance, runtime eligibility, fee budget)
- **Live map** — Leaflet dark-mode map with animated pins; urgent deadlines
  (≤ 14 days) pulse with a rose ring
- **Flights** — Google Flights data via Serpapi, falls back to a distance-based
  estimate; resolves your city to the nearest IATA airport automatically
- **Hotels** — Booking.com scrape or estimate, filtered to within X miles of
  the venue
- **Cars** — Rental estimates keyed to the festival's nearest airport
- **Rideshare** — Uber and Lyft deep-links with fare estimates from your
  pickup point to the venue
- **FilmFreeway sync** — nightly background job refreshes deadlines and fees
  from each festival's FilmFreeway page
- **URL sharing** — your search state (origin, filters, dates) is encoded in
  the URL hash so searches are bookmarkable and shareable with no account needed
- **Mobile layout** — bottom-sheet filter panel at ≤ 640 px; FAB to open it

---

## Prerequisites

- **Python 3.11 or newer** (3.12+ recommended; 3.14 works but emits a
  deprecation warning about the Windows event loop policy)
- **Git**
- Windows, macOS, or Linux

No Node.js, no build step. The frontend is plain HTML + JS served by FastAPI.

---

## Installation

### Windows — one command

```bat
git clone https://github.com/YOUR_USERNAME/reel-routes.git
cd reel-routes
start.bat
```

`start.bat` handles everything:
1. Creates a Python virtual environment in `backend/.venv`
2. Installs all dependencies from `backend/requirements.txt`
3. Copies `backend/.env.example` → `backend/.env` on first run
4. Starts the server

The app will open at **http://127.0.0.1:8000**.

### macOS / Linux

```bash
git clone https://github.com/YOUR_USERNAME/reel-routes.git
cd reel-routes/backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # edit NOMINATIM_EMAIL before running

uvicorn app.main:app --reload
```

The app will be at **http://127.0.0.1:8000** and the interactive API docs at
**http://127.0.0.1:8000/docs**.

---

## Configuration

`backend/.env` is created automatically on first run from `.env.example`. Open
it and set at minimum your email address (required by OpenStreetMap's Nominatim
geocoding policy):

```env
NOMINATIM_EMAIL=you@example.com
```

### All variables

| Variable | Default | Description |
|---|---|---|
| `NOMINATIM_EMAIL` | *(required)* | Your email — OpenStreetMap requires this for geocoding requests |
| `SERPAPI_KEY` | *(empty)* | Enables real Google Flights data. Get a free key (100 searches/month) at [serpapi.com](https://serpapi.com/) |
| `ENABLE_LIVE_SCRAPING` | `False` | Set to `True` to enable Playwright scrapers for hotels and car rentals |

When `SERPAPI_KEY` is empty or `ENABLE_LIVE_SCRAPING` is `False`, the app uses
distance-based estimates instead. The UI shows an `ESTIMATE` or `LIVE` badge
next to each data source so you always know which is which. If a live scrape
fails, it silently falls back to an estimate — the app never returns an error
to the user.

---

## Using the app

1. **Enter your origin** — type a city name (e.g. `Atlanta, GA`) or a US ZIP
   code in the search box and select from the autocomplete dropdown.

2. **Set your filters** — adjust genre chips, maximum runtime, submission fee
   cap, search radius, and the deadline date window. All filters update live.

3. **Click Search** — matching festivals appear as pins on the map and as cards
   in the left panel, sorted by fit score.

4. **Open a festival** — click a map pin or a card to open the detail drawer.
   The drawer shows the full festival info plus tabs for:
   - **Flights** — enter a departure date to get flight options and a booking link
   - **Hotels** — nearby hotels with nightly rates and booking links
   - **Cars** — rental options from the festival's nearest airport
   - **Rideshare** — Uber / Lyft estimates and deep-links from your current location

5. **Route to venue** — click the car icon on any hotel card to show the driving
   route on the map.

6. **Share your search** — click **Share ↗** in the drawer header to copy a URL
   that restores your exact search (origin, filters, dates).

### Deadlines

Festivals with a submission deadline within 14 days get a pulsing rose ring on
the map and a **CLOSING SOON** badge on their card. Deadlines are pulled from
the festival database and refreshed nightly from FilmFreeway.

---

## Getting live flight data (Serpapi)

The free tier gives you 100 Google Flights searches per month — enough for
regular use.

1. Sign up at [serpapi.com](https://serpapi.com/) and copy your API key.
2. Open `backend/.env` and set:
   ```env
   SERPAPI_KEY=your_key_here
   ```
3. Restart the server. Flight cards will now show real prices and a direct
   booking link to Google Flights.

---

## Enabling live hotel and car scraping (Playwright)

This is optional. Without it, hotel and car prices are distance-based estimates.

1. Install Chromium:
   ```bash
   playwright install chromium
   ```
2. Set in `backend/.env`:
   ```env
   ENABLE_LIVE_SCRAPING=True
   ```
3. Restart the server.

> **Note:** Booking.com and other metasearch sites change their page structure
> frequently. The CSS selectors in `backend/app/scrapers/hotels.py` may need
> occasional tuning. Always respect a site's `robots.txt` and Terms of Service.
> Keep the scrape cache TTL high (default: 6 hours) to avoid hammering servers.

---

## Adding or editing festivals

Festival data lives in SQLite (seeded on first run from
`backend/app/data/festivals.json`). You can:

**Add via the API** (no restart needed):
```bash
curl -X POST http://127.0.0.1:8000/api/admin/festivals \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Festival",
    "city": "Chicago, IL",
    "lat": 41.8781,
    "lng": -87.6298,
    "airport": "ORD",
    "filmfreeway_url": "https://filmfreeway.com/myfestival",
    "genres": ["Drama", "Documentary"],
    "max_runtime": 90,
    "base_fee": 40,
    "deadlines": [{"label": "Regular", "date": "2027-03-15"}],
    "tier": 2,
    "oscar_qual": false
  }'
```

Newly added festivals get `status: active` by default and appear on the map
immediately.

**Edit `festivals.json`** to add many festivals at once, then delete
`backend/reel_routes.db` and restart the server to re-seed from the file.

**Trigger a FilmFreeway refresh** (updates deadlines and fees for all festivals
that have a FilmFreeway URL):
```bash
curl -X POST http://127.0.0.1:8000/api/admin/field-refresh
```

---

## Running tests

```bash
cd backend
python -m pytest tests/ -v
```

Output should show **38 tests passing**:

| Test file | What it covers |
|---|---|
| `tests/test_unit.py` | `haversine_mi` distance math, rideshare fare estimates, fit-score formula |
| `tests/test_contract.py` | Every `/api/*` route — correct HTTP status codes and documented response shapes |

The contract tests spin up a full in-process FastAPI instance with a temporary
SQLite DB, so they don't need the server running and don't touch your real data.

---

## Project structure

```
reel-routes/
├── start.bat                    # Windows one-command launcher
├── backend/
│   ├── .env.example             # Copy to .env and configure
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py              # FastAPI app, all routes, serves the frontend
│   │   ├── config.py            # pydantic-settings (reads .env)
│   │   ├── models.py            # shared response types
│   │   ├── db.py                # SQLAlchemy async engine + FestivalRow model
│   │   ├── geocode.py           # Nominatim ZIP / City,State autocomplete
│   │   ├── scheduler.py         # APScheduler — nightly FilmFreeway sync
│   │   └── scrapers/
│   │       ├── base.py          # shared cache, geo math, Playwright helper
│   │       ├── filmfreeway.py   # scrapes deadlines + fees from FilmFreeway
│   │       ├── flights.py       # Serpapi (Google Flights) + estimate fallback
│   │       ├── hotels.py        # Booking.com scrape + estimate
│   │       └── transport.py     # car rentals + Uber/Lyft estimates
│   ├── data/
│   │   └── festivals.json       # seed data (loaded into SQLite on first run)
│   └── tests/
│       ├── test_unit.py
│       └── test_contract.py
└── frontend/
    ├── index.html               # app shell
    ├── css/styles.css           # dark cinematic theme
    └── js/
        ├── api.js               # backend client — one place for the base URL
        └── app.js               # map, search, detail panel, URL sharing
```

---

## API reference

All endpoints are also available with live try-it UI at
**http://127.0.0.1:8000/docs**.

### Public

| Method | Path | Parameters | Returns |
|---|---|---|---|
| GET | `/api/health` | — | `{ ok, live_scraping, festivals_total, festivals_active }` |
| GET | `/api/geocode` | `q` (min 3 chars), `limit` | list of `{ label, secondary, lat, lng }` |
| GET | `/api/festivals` | `lat`, `lng`, `radius_mi`, `genres`, `runtime`, `fee_budget`, `date_from`, `date_to` | list of festival objects with `dist_mi` and `fit` (0–100) |
| GET | `/api/festivals/{id}/refresh` | — | `{ live, scraped, festival }` |
| GET | `/api/flights` | `origin`, `fid`, `date`, `origin_lat`, `origin_lng` | `{ live, offers: [{ carrier, price, stops, depart, duration, booking_url }] }` |
| GET | `/api/hotels` | `fid`, `radius_mi`, `checkin`, `nights`, `rooms` | `{ live, hotels: [{ name, nightly, dist_mi, booking_url }] }` |
| GET | `/api/cars` | `fid`, `pickup`, `dropoff` | `{ live, cars: [{ car_class, daily, booking_url }] }` |
| GET | `/api/rideshare` | `plat`, `plng`, `fid` | `{ estimates: [{ service, est_low, est_high, distance_mi, deeplink }] }` |

### Admin

> These endpoints have no authentication. Do not expose port 8000 to the
> internet without adding an API-key middleware first.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/admin/festivals` | List all festivals (all statuses) |
| POST | `/api/admin/festivals` | Add a festival (JSON body) |
| POST | `/api/admin/festivals/{id}/approve` | Set status → active |
| POST | `/api/admin/festivals/{id}/deactivate` | Set status → inactive |
| POST | `/api/admin/festivals/{id}/reactivate` | Restore inactive festival |
| POST | `/api/admin/sync` | Trigger catalog sync (background) |
| POST | `/api/admin/field-refresh` | Trigger FilmFreeway refresh for all festivals (background) |

---

## Fit score explained

Each result gets a score out of 100 based on how well the festival matches your
filters:

| Signal | Points |
|---|---|
| Genre matches one of your selected genres | 35 |
| Deadline falls within your date window | 25 |
| Festival is within your radius | 20 |
| Runtime is within the festival's limit | 10 |
| Submission fee is within your budget | 10 |

Results are sorted by score descending, then by distance.

---

## Troubleshooting

**`uvicorn: command not found` / `python: command not found`**
Make sure you activated the virtual environment first, or use `start.bat` on
Windows which handles this automatically.

**Geocoding returns no results**
Set `NOMINATIM_EMAIL` in `.env` to a real email address. Nominatim blocks
requests with the placeholder value.

**Flights show estimates instead of real prices**
Either `SERPAPI_KEY` is empty or the key has hit its monthly limit (100 free
searches). Check your dashboard at [serpapi.com](https://serpapi.com/).

**Hotels / cars show estimates even with live scraping on**
The site's DOM changed, or the request was blocked. Check the server logs for
scraper errors. The app falls back to estimates automatically.

**Windows — `NotImplementedError` in server logs**
This is a known Python 3.14 / Windows issue with the default event loop. The
fix is already applied in `app/main.py`. If you see it anyway, make sure you
are running via `start.bat` or `uvicorn` directly (not `python main.py`).

**Test warning about `WindowsProactorEventLoopPolicy` deprecation**
Harmless — Python 3.14 deprecated this API, but it still works. The warning
will be removed once Python 3.16 ships a stable replacement.

---

## Contributing

Pull requests are welcome. A few guidelines:

- **Adding festivals** — edit `backend/app/data/festivals.json` and open a PR.
  Include the FilmFreeway URL so the nightly sync can keep deadlines current.
- **Scraper fixes** — selectors live in `app/scrapers/`. Add a FilmFreeway URL
  to a test festival and run `pytest -v` to verify the contract is intact.
- **New features** — open an issue first so we can discuss scope before you
  invest time building.
- **Code style** — Python: PEP 8, async-first. JS: no framework, keep it in
  `app.js`. No build tooling, please.

---

## License

MIT — see `LICENSE` for details.
