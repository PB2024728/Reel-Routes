/* API client — single place that knows the backend URL.
   When you deploy, change BASE to your server's origin. */
const API = (() => {
  const BASE = location.origin.includes("file://") || location.port === "5500"
    ? "http://127.0.0.1:8000"   // dev: backend on 8000, frontend on Live Server
    : "";                        // prod: served by FastAPI itself

  async function get(path, params = {}) {
    const url = new URL(BASE + path, location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${path} → ${r.status}`);
    return r.json();
  }

  return {
    health: () => get("/api/health"),
    geocode: (q, limit = 6) => get("/api/geocode", { q, limit }),
    festivals: (p) => get("/api/festivals", p),
    flights: (origin, fid, date, dist_mi, origin_lat, origin_lng) =>
      get("/api/flights", { origin, fid, date, dist_mi, origin_lat, origin_lng }),
    hotels: (fid, radius_mi, checkin, nights, rooms) =>
      get("/api/hotels", { fid, radius_mi, checkin, nights, rooms }),
    cars: (fid, pickup, dropoff) => get("/api/cars", { fid, pickup, dropoff }),
    rideshare: (plat, plng, fid) => get("/api/rideshare", { plat, plng, fid }),
  };
})();
