# Reel Routes — Updates & Ideas

A running log of planned changes, feature ideas, and notes. Add new entries at the top.

---

## 2026-06-28 — Initial brainstorm

### Quick wins
- [x] Fix `NOMINATIM_EMAIL` in `backend/.env` (currently `you@example.com`) to avoid Nominatim rate-limiting
- [x] Expand festivals — data moved to SQLite DB; JSON no longer the source of truth
- [x] Add unit tests for `haversine_mi`, `rideshare_estimates`, and the fit-score formula (called out in CLAUDE.md, zero coverage today)
- [x] Add "closing soon" badge on festival cards when a deadline is within 14 days (data already in JSON)

### Medium features
- [x] Wire up flight API — implemented Serpapi (Google Flights); set `SERPAPI_KEY` in `.env` to activate (100 free searches/mo at serpapi.com). Amadeus dropped — self-service portal decommissioned July 2026.
- [x] Save/share a trip via URL params — encode origin, dates, and filters in the URL so searches are shareable/bookmarkable, no DB needed
- [x] Deadline urgency highlighting — pulsing rose ring on map markers + "CLOSING SOON" badge on cards for deadlines within 14 days

### Bigger changes
- [ ] User accounts + saved festivals — FastAPI + SQLite auth layer so users can bookmark festivals and return to a shortlist
- [x] FilmFreeway nightly sync — concurrent field refresh (Semaphore 4) + `POST /api/admin/field-refresh` manual trigger added
- [x] Mobile layout improvements — bottom-sheet pattern at ≤640px; filters FAB on map; overlay tap-to-close; sheet auto-closes after search

### Dev / infra
- [x] Set up GitHub repo (in progress as of today)
- [x] Add contract tests verifying every `/api/*` route returns the documented shape
