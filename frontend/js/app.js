/* Reel Routes frontend — talks to the FastAPI backend via API (api.js). */
const UI = (() => {
  const ALL_GENRES = ["Drama","Comedy","Documentary","Horror","Thriller","Animation","Experimental"];
  const selectedGenres = new Set(["Drama"]);
  let base = { lat: 34.075, lng: -84.294, label: "Alpharetta, GA" };
  let results = [], markers = [], baseMarker = null, radiusCircle = null;
  let map;

  /* ---------- map ---------- */
  function initMap() {
    map = L.map("map", { zoomControl: true, attributionControl: false }).setView([39.5,-98.35], 4);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { maxZoom: 19, subdomains: "abcd" }).addTo(map);
    setTimeout(() => map.invalidateSize(), 200);
    window.addEventListener("resize", () => map.invalidateSize());
  }

  /* ---------- controls ---------- */
  function buildControls() {
    const box = document.getElementById("genreChips");
    ALL_GENRES.forEach(g => {
      const el = document.createElement("div");
      el.className = "chip" + (selectedGenres.has(g) ? " on" : "");
      el.textContent = g;
      el.onclick = () => { el.classList.toggle("on");
        selectedGenres.has(g) ? selectedGenres.delete(g) : selectedGenres.add(g); };
      box.appendChild(el);
    });
    const r = document.getElementById("radius"), rv = document.getElementById("radiusVal");
    r.oninput = () => rv.textContent = r.value + " mi";
    const lr = document.getElementById("lodgeRad"), lrv = document.getElementById("lodgeRadVal");
    lr.oninput = () => lrv.textContent = lr.value + " mi";
    document.getElementById("baseSearch").value = base.label;
  }

  /* ---------- geocode autocomplete (Yelp/Fandango style) ---------- */
  function wireGeocode() {
    const input = document.getElementById("baseSearch");
    const list = document.getElementById("geoResults");
    const status = document.getElementById("geoStatus");
    let timer = null, active = -1, items = [];

    function render() {
      if (!items.length) { list.classList.remove("show"); return; }
      list.innerHTML = items.map((d, i) =>
        `<div class="geo-item ${i===active?'active':''}" data-i="${i}">
           <b>${d.label}</b><small>${d.secondary}</small></div>`).join("");
      list.classList.add("show");
      list.querySelectorAll(".geo-item").forEach(el =>
        el.onclick = () => choose(+el.dataset.i));
    }
    function choose(i) {
      const d = items[i]; if (!d) return;
      base = { lat: d.lat, lng: d.lng, label: d.label };
      input.value = d.label; list.classList.remove("show");
      status.textContent = "✓ Base set";
      runSearch();
    }
    input.addEventListener("input", () => {
      clearTimeout(timer); active = -1;
      const q = input.value.trim();
      if (q.length < 3) { list.classList.remove("show"); status.textContent=""; return; }
      status.textContent = "Searching…";
      timer = setTimeout(async () => {
        try {
          items = await API.geocode(q);
          status.textContent = items.length ? "" : "No matches — try another spelling.";
          render();
        } catch (e) {
          status.textContent = "Lookup unavailable. Is the backend running on :8000?";
        }
      }, 300);
    });
    input.addEventListener("keydown", (e) => {
      if (!items.length) return;
      if (e.key === "ArrowDown") { active = Math.min(active+1, items.length-1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { active = Math.max(active-1, 0); render(); e.preventDefault(); }
      else if (e.key === "Enter") { choose(active >= 0 ? active : 0); e.preventDefault(); }
      else if (e.key === "Escape") list.classList.remove("show");
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".geo-wrap")) list.classList.remove("show");
    });
  }

  /* ---------- search ---------- */
  async function runSearch() {
    const params = {
      lat: base.lat, lng: base.lng,
      radius_mi: +document.getElementById("radius").value,
      genres: [...selectedGenres].join(","),
      runtime: +document.getElementById("runtime").value,
      fee_budget: +document.getElementById("festBudget").value,
      date_from: document.getElementById("dateFrom").value,
      date_to: document.getElementById("dateTo").value,
    };
    try {
      results = await API.festivals(params);
    } catch (e) {
      document.getElementById("cardList").innerHTML =
        `<div class="empty">Couldn't reach the backend.<br><br>Start it with:<br>
         <code style="color:var(--amber)">uvicorn app.main:app --reload</code><br>
         from the <b>backend</b> folder, then retry.</div>`;
      document.getElementById("drawer").classList.add("open");
      return;
    }
    drawMap(params.radius_mi); renderCards();
    document.getElementById("matchCount").textContent = results.length;
    openDrawer();
  }

  function drawMap(radius) {
    markers.forEach(m => map.removeLayer(m)); markers = [];
    if (baseMarker) map.removeLayer(baseMarker);
    if (radiusCircle) map.removeLayer(radiusCircle);
    baseMarker = L.marker([base.lat, base.lng], { icon: L.divIcon({ className:"",
      html:'<div class="pin-pulse" style="width:16px;height:16px;border:2px solid #0d0f14"></div>',
      iconSize:[16,16], iconAnchor:[8,8] }) }).addTo(map).bindPopup(`<b>Your base</b><br>${base.label}`);
    radiusCircle = L.circle([base.lat, base.lng], { radius: radius*1609, color:"#f4b740",
      weight:1, fillColor:"#f4b740", fillOpacity:.04, dashArray:"4 6" }).addTo(map);
    results.forEach((f, i) => {
      const color = f.tier===1?"#f4b740":f.tier===2?"#43c6b8":"#8a90a2";
      const m = L.marker([f.lat, f.lng], { icon: L.divIcon({ className:"",
        html:`<div class="pin-label" style="background:${color}">${i+1}</div>`,
        iconSize:[24,24], iconAnchor:[12,12] }) }).addTo(map);
      m.bindPopup(`<b style="font-size:14px">${f.name}</b><br>
        <span style="color:#8a90a2;font-size:12px">${f.city} · ${Math.round(f.dist_mi)} mi</span><br>
        <span style="color:#f4b740;font-size:12px">Fit ${f.fit}% · accepts ~${f.accept_rate}%</span><br>
        <a href="${f.filmfreeway_url}" target="_blank" rel="noopener">Apply on FilmFreeway →</a>`);
      m.on("click", () => openDetail(f.id));
      markers.push(m);
    });
    if (results.length) {
      const grp = L.featureGroup([baseMarker, ...markers]);
      map.fitBounds(grp.getBounds().pad(.2));
    } else map.setView([base.lat, base.lng], 6);
    setTimeout(() => map.invalidateSize(), 50);
  }

  function renderCards() {
    const box = document.getElementById("cardList");
    document.getElementById("drawerCount").textContent =
      results.length ? `${results.length} festivals · sorted by fit` : "No matches";
    if (!results.length) {
      box.innerHTML = '<div class="empty">No festivals match. Widen radius, dates, or genres.</div>';
      return;
    }
    const travelBudget = +document.getElementById("travelBudget").value;
    box.innerHTML = results.map((f, i) => {
      const tcls = f.tier===1?"t1":f.tier===2?"t2":"t3";
      const tlab = f.tier===1?"TIER 1":f.tier===2?"TIER 2":"TIER 3";
      const next = f.deadlines.map(d=>d.date).filter(d=>new Date(d)>=new Date()).sort()[0]||f.deadlines[0].date;
      return `<div class="fcard">
        <div class="top" onclick="UI.openDetail(${f.id})">
          <div><h3>${i+1}. ${f.name}</h3><div class="loc">${f.city} · ${Math.round(f.dist_mi)} mi away</div></div>
          <span class="tier ${tcls}">${tlab}</span>
        </div>
        <div class="meta-grid">
          <div class="meta"><div class="k">Accept rate</div><div class="v ${f.accept_rate<5?'hot':''}">~${f.accept_rate}%</div></div>
          <div class="meta"><div class="k">Next deadline</div><div class="v">${fmtDate(next)}</div></div>
          <div class="meta"><div class="k">Entry fee</div><div class="v">$${f.base_fee}</div></div>
          <div class="meta"><div class="k">Oscar-qual</div><div class="v ${f.oscar_qual?'good':''}">${f.oscar_qual?'Yes':'No'}</div></div>
        </div>
        <div class="fit-bar"><i style="width:${f.fit}%"></i></div>
        <div class="fit-label"><span>Fit score</span><span>${f.fit}%</span></div>
        <div class="card-actions">
          <a class="mini-btn apply" href="${f.filmfreeway_url}" target="_blank" rel="noopener">Apply on FilmFreeway ↗</a>
          <span class="mini-btn detail" onclick="UI.openDetail(${f.id})">Plan trip</span>
        </div>
      </div>`;
    }).join("");
  }

  /* ---------- detail with live travel ---------- */
  async function openDetail(id) {
    const f = results.find(x => x.id === id);
    if (!f) return;
    const party = +document.getElementById("party").value;
    const nights = +document.getElementById("nights").value;
    const lodgeRad = +document.getElementById("lodgeRad").value;
    const rooms = Math.ceil(party / 2);
    const firstDeadline = f.deadlines.map(d=>d.date).sort()[0];
    const tlab = f.tier===1?"Tier 1 · Major":f.tier===2?"Tier 2 · Regional":"Tier 3 · Niche";
    const deadlineRows = f.deadlines.map(d =>
      `<div class="kv"><span class="lab">${d.label} deadline</span><span class="val">${fmtDate(d.date)}</span></div>`).join("");

    document.getElementById("detail").classList.add("open");
    document.getElementById("drawer").classList.add("open");
    document.getElementById("detailBody").innerHTML = `
      <h2>${f.name}</h2>
      <div class="sub">${f.city} · ${tlab}${f.oscar_qual?' · ★ Oscar-qualifying':''}</div>
      <a class="apply-cta" href="${f.filmfreeway_url}" target="_blank" rel="noopener">Apply on FilmFreeway ↗</a>

      <div class="section-t">Festival statistics</div>
      <div class="kv"><span class="lab">Acceptance rate</span><span class="val" style="color:${f.accept_rate<5?'var(--rose)':'var(--teal)'}">~${f.accept_rate}%</span></div>
      <div class="kv"><span class="lab">Annual attendance</span><span class="val">${f.attendees.toLocaleString()}</span></div>
      <div class="kv"><span class="lab">Entry fee</span><span class="val">$${f.base_fee}</span></div>
      <div class="kv"><span class="lab">Distance from base</span><span class="val">${Math.round(f.dist_mi)} mi</span></div>
      <div class="kv"><span class="lab">Genres</span><span class="val" style="font-family:'DM Sans'">${f.genres.join(', ')}</span></div>

      <div class="section-t">Deadlines</div>
      <div class="deadline-list">${deadlineRows}</div>

      <div class="section-t">Flights <span id="flTag" class="live-tag off">…</span></div>
      <div id="flightBox"><div class="loading-row">Loading flights…</div></div>

      <div class="section-t">Hotels within ${lodgeRad} mi of venue <span id="htTag" class="live-tag off">…</span></div>
      <div id="hotelBox"><div class="loading-row">Loading hotels…</div></div>

      <div class="section-t">Car rental <span id="carTag" class="live-tag off">…</span></div>
      <div id="carBox"><div class="loading-row">Loading cars…</div></div>

      <div class="section-t">Rideshare from your base</div>
      <div id="rideBox"><div class="loading-row">Estimating…</div></div>

      <div class="placeholder-note">Flights/hotels/cars are estimates until live scraping is enabled on the backend (ENABLE_LIVE_SCRAPING=True). Booking links and rideshare deep-links work now.</div>
    `;
    map.setView([f.lat, f.lng], 8, { animate: true });

    // fire all travel calls in parallel
    loadFlights(f, firstDeadline, party);
    loadHotels(f, lodgeRad, firstDeadline, nights, rooms);
    loadCars(f, firstDeadline, nights);
    loadRideshare(f);
  }

  async function loadFlights(f, date, party) {
    try {
      const d = await API.flights(base.label, f.id, date, f.dist_mi);
      setTag("flTag", d.live);
      document.getElementById("flightBox").innerHTML = d.offers.map(o =>
        `<div class="flight-card"><div class="info"><h4>${o.carrier}</h4>
          <small>${base.label.split(",")[0]} → ${f.city.split(",")[0]} (${f.airport}) · ${o.stops} stop(s)</small></div>
          <div class="price"><b>$${Math.round(o.price).toLocaleString()}</b>
          <a href="${o.booking_url}" target="_blank" rel="noopener">Book ↗</a></div></div>`).join("");
    } catch { document.getElementById("flightBox").innerHTML = '<div class="loading-row">Flights unavailable.</div>'; }
  }
  async function loadHotels(f, radius, checkin, nights, rooms) {
    try {
      const d = await API.hotels(f.id, radius, checkin, nights, rooms);
      setTag("htTag", d.live);
      const box = document.getElementById("hotelBox");
      box.innerHTML = d.hotels.length ? d.hotels.map(h =>
        `<div class="lodge-card"><div class="info"><h4>${h.name}</h4>
          <small>${h.dist_mi!=null?`<span class="dist-badge">${h.dist_mi} mi from venue</span> · `:''}${nights} nights × ${rooms} room(s)${h.rating?` · ★${h.rating}`:''}</small></div>
          <div class="price"><b>$${h.nightly}/nt</b><a href="${h.booking_url}" target="_blank" rel="noopener">Book ↗</a></div></div>`).join("")
        : '<div class="loading-row">No lodging within this radius — widen the slider.</div>';
    } catch { document.getElementById("hotelBox").innerHTML = '<div class="loading-row">Hotels unavailable.</div>'; }
  }
  async function loadCars(f, pickup, nights) {
    const dropoff = addDays(pickup, nights);
    try {
      const d = await API.cars(f.id, pickup, dropoff);
      setTag("carTag", d.live);
      document.getElementById("carBox").innerHTML = d.cars.map(c =>
        `<div class="car-card"><div class="info"><h4>${c.car_class}</h4>
          <small>Pick up at ${f.airport} · ${nights} days</small></div>
          <div class="price"><b>$${c.daily}/day</b><a href="${c.booking_url}" target="_blank" rel="noopener">Book ↗</a></div></div>`).join("");
    } catch { document.getElementById("carBox").innerHTML = '<div class="loading-row">Cars unavailable.</div>'; }
  }
  async function loadRideshare(f) {
    try {
      const d = await API.rideshare(base.lat, base.lng, f.id);
      document.getElementById("rideBox").innerHTML = d.estimates.map(e =>
        `<div class="ride-card"><div class="info"><h4>${e.service}
          <span class="ride-badge">${e.distance_mi} mi</span></h4>
          <small>${e.note}</small></div>
          <div class="price"><b>$${e.est_low}–$${e.est_high}</b>
          <a href="${e.deeplink}" target="_blank" rel="noopener">Open ${e.service} ↗</a></div></div>`).join("");
    } catch { document.getElementById("rideBox").innerHTML = '<div class="loading-row">Rideshare unavailable.</div>'; }
  }

  /* ---------- helpers ---------- */
  function setTag(id, live) {
    const el = document.getElementById(id); if (!el) return;
    el.textContent = live ? "LIVE" : "ESTIMATE";
    el.className = "live-tag " + (live ? "on" : "off");
  }
  function fmtDate(s){ return new Date(s+"T00:00").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}); }
  function addDays(iso, n){ const d=new Date(iso); d.setDate(d.getDate()+n); return d.toISOString().slice(0,10); }
  function openDrawer(){ document.getElementById("drawer").classList.add("open"); }
  function closeDrawer(){ document.getElementById("drawer").classList.remove("open"); document.getElementById("detail").classList.remove("open"); }
  function closeDetail(){ document.getElementById("detail").classList.remove("open"); }
  function resetView(){ map.setView([39.5,-98.35],4); setTimeout(()=>map.invalidateSize(),50); }

  /* ---------- boot ---------- */
  async function boot() {
    initMap(); buildControls(); wireGeocode();
    try {
      const h = await API.health();
      document.getElementById("modeFlag").textContent = h.live_scraping ? "LIVE" : "ESTIMATE";
    } catch {
      document.getElementById("modeFlag").textContent = "OFFLINE";
    }
    runSearch();
  }

  return { boot, runSearch, openDetail, openDrawer, closeDrawer, closeDetail, resetView };
})();

window.addEventListener("load", UI.boot);
