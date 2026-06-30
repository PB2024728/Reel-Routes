/* Reel Routes frontend — talks to the FastAPI backend via API (api.js). */
const UI = (() => {
  const ALL_GENRES = ["Action","Animation","Art House","Biographical","Comedy","Crime","Documentary","Drama","Experimental","Family","Fantasy","Horror","LGBTQ+","Music Video","Mystery","Romance","Sci-Fi","Thriller","World Cinema"];
  const ALL_LANGUAGES = ["Arabic","English","French","German","Hindi","Italian","Japanese","Korean","Mandarin","Persian","Portuguese","Russian","Spanish","Swedish","Turkish","Other"];
  const selectedGenres = new Set(["Drama"]);
  const selectedLanguages = new Set(["English"]);
  let base = { lat: 34.075, lng: -84.294, label: "Alpharetta, GA" };
  let results = [], markers = [], baseMarker = null, radiusCircle = null;
  let currentTab = "matches";
  let currentDetailId = null;
  let detailCosts = {};
  let map, hotelMarker = null, hotelRouteLine = null;
  const travelNeeds = { flights: true, hotel: true, car: true, ride: true };
  const travelLimits = { flight: 800, hotel: 200, car: 100 };

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
    const langBox = document.getElementById("langChips");
    ALL_LANGUAGES.forEach(l => {
      const el = document.createElement("div");
      el.className = "chip" + (selectedLanguages.has(l) ? " on" : "");
      el.textContent = l;
      el.onclick = () => { el.classList.toggle("on");
        selectedLanguages.has(l) ? selectedLanguages.delete(l) : selectedLanguages.add(l); };
      langBox.appendChild(el);
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
      languages: [...selectedLanguages].join(","),
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
    syncToURL();
    // Close mobile filter sheet after search completes
    if (window.innerWidth <= 640) {
      document.querySelector(".controls")?.classList.remove("mobile-open");
      const ov = document.getElementById("mobileOverlay");
      if (ov) ov.style.display = "none";
    }
    openDrawer();
    // If a detail panel is open, refresh it with the new results (updated origin, dist_mi, etc.)
    if (currentDetailId !== null) {
      const stillVisible = results.find(x => x.id === currentDetailId);
      if (stillVisible) {
        openDetail(currentDetailId);
      } else {
        // Festival is no longer in results (e.g. now outside the radius)
        document.getElementById("detail").classList.remove("open");
        currentDetailId = null;
      }
    }
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
    const today = new Date(); today.setHours(0,0,0,0);
    results.forEach((f, i) => {
      const color = f.tier===1?"#f4b740":f.tier===2?"#43c6b8":"#8a90a2";
      const urgent = (f.deadlines||[]).some(d => {
        const days = Math.ceil((new Date(d.date+"T00:00") - today) / 86400000);
        return days >= 0 && days <= 14;
      });
      const pinInner = `<div class="pin-label" style="background:${color}">${i+1}</div>`;
      const pinHtml = urgent ? `<div class="pin-urgent-wrap">${pinInner}</div>` : pinInner;
      const m = L.marker([f.lat, f.lng], { icon: L.divIcon({ className:"",
        html: pinHtml,
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
    const today = new Date(); today.setHours(0,0,0,0);
    const savedSnap = getSaved();
    box.innerHTML = results.map((f, i) => {
      const tcls = f.tier===1?"t1":f.tier===2?"t2":"t3";
      const tlab = f.tier===1?"TIER 1":f.tier===2?"TIER 2":"TIER 3";
      const next = f.deadlines.map(d=>d.date).filter(d=>new Date(d+"T00:00")>=today).sort()[0]||f.deadlines[0].date;
      const daysUntil = Math.ceil((new Date(next+"T00:00") - today) / 86400000);
      const closingSoon = daysUntil >= 0 && daysUntil <= 14;
      const genreChips = f.genres.map(g=>`<span class="genre-tag">${g}</span>`).join("");
      const saved = String(f.id) in savedSnap;
      const dlPills = f.deadlines.map(d => {
        const past = new Date(d.date+"T00:00") < today;
        return `<span class="dl-pill${past?" past":""}">${d.label} · ${fmtDate(d.date)}</span>`;
      }).join("");
      return `<div class="fcard">
        <div class="top" onclick="UI.openDetail(${f.id})">
          <div><h3>${i+1}. ${f.name}${closingSoon?` <span class="closing-soon">CLOSING SOON</span>`:''}</h3><div class="loc">${f.city} · ${Math.round(f.dist_mi)} mi away</div></div>
          <div style="display:flex;align-items:center;gap:6px;flex:none">
            <button class="save-btn${saved?' saved':''}" data-id="${f.id}" onclick="event.stopPropagation();UI.toggleSave(${f.id})" title="${saved?'Remove from list':'Save to list'}">${saved?'★':'☆'}</button>
            <span class="tier ${tcls}">${tlab}</span>
          </div>
        </div>
        <div class="card-genres">${genreChips}</div>
        <div class="meta-grid">
          <div class="meta"><div class="k">Festival dates</div><div class="v" style="color:var(--teal)">${f.festival_start?fmtDate(f.festival_start)+(f.festival_end?" – "+fmtDate(f.festival_end):""):"TBA"}</div></div>
          <div class="meta"><div class="k">Entry fee</div><div class="v">$${f.base_fee}</div></div>
          <div class="meta"><div class="k">Accept rate</div><div class="v ${f.accept_rate<5?"hot":""}">~${f.accept_rate}%</div></div>
          <div class="meta"><div class="k">Oscar-qual</div><div class="v ${f.oscar_qual?"good":""}">${f.oscar_qual?"Yes":"No"}</div></div>
        </div>
        <div class="deadlines-row">
          <div class="dl-row-label">Submission deadlines</div>
          <div class="dl-pills">${dlPills}</div>
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
    // Prefer live results (has fresh dist_mi); fall back to saved data
    const f = results.find(x => x.id === id) || getSaved()[String(id)];
    if (!f) return;
    currentDetailId = id;
    const party = +document.getElementById("party").value;
    const lodgeRad = +document.getElementById("lodgeRad").value;
    const rooms = Math.ceil(party / 2);
    const tlab = f.tier===1?"Tier 1 · Major":f.tier===2?"Tier 2 · Regional":"Tier 3 · Niche";
    const today = new Date(); today.setHours(0,0,0,0);

    // Use actual festival dates when available; fall back to first deadline + sidebar nights
    const checkinDate = f.festival_start || f.deadlines.map(d=>d.date).sort()[0];
    const tripNights = (f.festival_start && f.festival_end)
      ? Math.max(1, Math.ceil((new Date(f.festival_end+"T00:00") - new Date(f.festival_start+"T00:00")) / 86400000))
      : +document.getElementById("nights").value;

    const deadlineRows = f.deadlines.map(d => {
      const dDate = new Date(d.date+"T00:00");
      const past = dDate < today;
      const daysLeft = Math.ceil((dDate - today) / 86400000);
      const urgency = !past && daysLeft <= 14 ? ` <span class="closing-soon">in ${daysLeft}d</span>` : "";
      return `<div class="kv${past?' dl-past':''}"><span class="lab">${d.label} deadline</span><span class="val">${fmtDate(d.date)}${urgency}</span></div>`;
    }).join("");
    const genreChipsDetail = f.genres.map(g=>`<span class="genre-tag">${g}</span>`).join("");
    const runtimeStr = f.max_runtime < 9999 ? `${f.max_runtime} min max` : "No limit";
    const festDatesStr = f.festival_start
      ? `${fmtDate(f.festival_start)}${f.festival_end ? " – " + fmtDate(f.festival_end) : ""} · ${tripNights} night${tripNights!==1?"s":""}`
      : "Dates TBA";

    // Reset cost state for this festival
    detailCosts = { fee: f.base_fee, flightPer: null, hotelNightly: null, carDaily: null };

    document.getElementById("detail").classList.add("open");
    document.getElementById("drawer").classList.add("open");
    const detailSaved = isSaved(f.id);
    document.getElementById("detailBody").innerHTML = `
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px">
        <div>
          <h2>${f.name}</h2>
          <div class="sub">${f.city} · ${tlab}${f.oscar_qual?' · ★ Oscar-qualifying':''}</div>
        </div>
        <button class="save-btn${detailSaved?' saved':''}" data-id="${f.id}"
          onclick="UI.toggleSave(${f.id})"
          title="${detailSaved?'Remove from list':'Save to list'}"
          style="font-size:26px;flex:none;margin-top:4px">${detailSaved?'★':'☆'}</button>
      </div>
      <a class="apply-cta" href="${f.filmfreeway_url}" target="_blank" rel="noopener">Apply on FilmFreeway ↗</a>

      <div class="section-t">Genres</div>
      <div class="detail-genres">${genreChipsDetail}</div>

      <div class="section-t">Festival details</div>
      <div class="kv"><span class="lab">Festival dates</span><span class="val" style="color:var(--teal)">${festDatesStr}</span></div>
      <div class="kv"><span class="lab">Acceptance rate</span><span class="val" style="color:${f.accept_rate<5?'var(--rose)':'var(--teal)'}">~${f.accept_rate}%</span></div>
      <div class="kv"><span class="lab">Annual attendance</span><span class="val">${f.attendees.toLocaleString()}</span></div>
      <div class="kv"><span class="lab">Entry fee</span><span class="val">$${f.base_fee}</span></div>
      <div class="kv"><span class="lab">Max runtime</span><span class="val">${runtimeStr}</span></div>
      <div class="kv"><span class="lab">Oscar-qualifying</span><span class="val" style="color:${f.oscar_qual?'var(--teal)':'var(--muted)'}">${f.oscar_qual?'Yes':'No'}</span></div>
      <div class="kv"><span class="lab">Distance from base</span><span class="val">${Math.round(f.dist_mi)} mi</span></div>

      <div class="section-t">Submission deadlines</div>
      <div class="deadline-list">${deadlineRows}</div>

      <div class="section-t">Trip Cost Estimate
        <span style="font-family:'DM Sans';font-size:10px;color:var(--faint);font-weight:400;letter-spacing:0;text-transform:none;margin-left:6px">cheapest available option</span>
      </div>
      <div class="trip-inputs">
        <label class="ti-field"><span>People</span><input type="number" id="detailParty" value="${party}" min="1" max="20" oninput="UI.updateDetailCost()"></label>
        <label class="ti-field"><span>Nights</span><input type="number" id="detailNights" value="${tripNights}" min="1" oninput="UI.updateDetailCost()"></label>
        <label class="ti-field"><span>Hotel rooms</span><input type="number" id="detailRooms" value="${rooms}" min="0" oninput="UI.updateDetailCost()"></label>
        <label class="ti-field"><span>Rental cars</span><input type="number" id="detailCars" value="1" min="0" oninput="UI.updateDetailCost()"></label>
      </div>
      <div class="trip-cost">
        <div class="tc-row"><span class="tc-lab">Submission fee</span><span class="tc-val">$${f.base_fee}</span></div>
        <div class="tc-row" id="tcRowFlight"${travelNeeds.flights?'':' style="display:none"'}><span class="tc-lab" id="tcFlightLab">Flights</span><span class="tc-val tc-pending" id="tcFlight">loading…</span></div>
        <div class="tc-row" id="tcRowHotel"${travelNeeds.hotel?'':' style="display:none"'}><span class="tc-lab" id="tcHotelLab">Hotels</span><span class="tc-val tc-pending" id="tcHotel">loading…</span></div>
        <div class="tc-row" id="tcRowCar"${travelNeeds.car?'':' style="display:none"'}><span class="tc-lab" id="tcCarLab">Car rental</span><span class="tc-val tc-pending" id="tcCar">loading…</span></div>
        <div class="tc-row tc-grand"><span class="tc-lab">Est. Total</span><span class="tc-val" id="tcTotal">—</span></div>
      </div>

      <div id="secFlights"${travelNeeds.flights?'':' style="display:none"'}>
        <div class="section-t">Flights <span id="flTag" class="live-tag off">…</span></div>
        <div id="flightBox"><div class="loading-row">Loading flights…</div></div>
      </div>

      <div id="secHotel"${travelNeeds.hotel?'':' style="display:none"'}>
        <div class="section-t">Hotels within ${lodgeRad} mi <span id="htTag" class="live-tag off">…</span></div>
        <div id="hotelBox"><div class="loading-row">Loading hotels…</div></div>
      </div>

      <div id="secCar"${travelNeeds.car?'':' style="display:none"'}>
        <div class="section-t">Car rental <span id="carTag" class="live-tag off">…</span></div>
        <div id="carBox"><div class="loading-row">Loading cars…</div></div>
      </div>

      <div id="secRide"${travelNeeds.ride?'':' style="display:none"'}>
        <div class="section-t">Rideshare: lodging → venue (within ${lodgeRad} mi)</div>
        <div id="rideBox"><div class="loading-row">Estimating…</div></div>
      </div>

      <div class="placeholder-note">Flights/hotels/cars are estimates until live scraping is enabled on the backend (ENABLE_LIVE_SCRAPING=True). Booking links and rideshare deep-links work now.</div>
    `;
    clearHotelMap();
    map.setView([f.lat, f.lng], 8, { animate: true });

    // fire travel calls conditionally based on user needs
    if (travelNeeds.flights) loadFlights(f, checkinDate, party);
    else { detailCosts.flightPer = 0; updateDetailCost(); }
    if (travelNeeds.hotel) loadHotels(f, lodgeRad, checkinDate, tripNights, rooms);
    else { detailCosts.hotelNightly = 0; updateDetailCost(); }
    if (travelNeeds.car) loadCars(f, checkinDate, tripNights);
    else { detailCosts.carDaily = 0; updateDetailCost(); }
    if (travelNeeds.ride) loadRideshare(f, lodgeRad);
  }

  async function loadFlights(f, date, party) {
    try {
      const d = await API.flights(base.label, f.id, date, f.dist_mi, base.lat, base.lng);
      setTag("flTag", d.live);
      const filtered = d.offers.filter(o => o.price <= travelLimits.flight);
      if (!filtered.length && d.offers.length) {
        document.getElementById("flightBox").innerHTML = `<div class="budget-warn">No flights found within $${travelLimits.flight}/person budget — raise your limit to see options.</div>`;
        detailCosts.flightPer = 0; updateDetailCost(); return;
      }
      const display = filtered.length ? filtered : d.offers;
      document.getElementById("flightBox").innerHTML = display.map(o =>
        `<div class="flight-card"><div class="info"><h4>${o.carrier}</h4>
          <small>${base.label.split(",")[0]} → ${f.city.split(",")[0]} (${f.airport || "nearest airport"}) · ${o.stops} stop(s)</small></div>
          <div class="price"><b>$${Math.round(o.price).toLocaleString()}/person</b>
          <a href="${o.booking_url}" target="_blank" rel="noopener">Search Google Flights ↗</a></div></div>`).join("");
      const prices = display.map(o => o.price).filter(p => isFinite(p));
      if (prices.length) { detailCosts.flightPer = Math.min(...prices); updateDetailCost(); }
    } catch {
      document.getElementById("flightBox").innerHTML = '<div class="loading-row">Flights unavailable.</div>';
      detailCosts.flightPer = 0; updateDetailCost();
    }
  }
  async function loadHotels(f, radius, checkin, nights, rooms) {
    try {
      const d = await API.hotels(f.id, radius, checkin, nights, rooms);
      setTag("htTag", d.live);
      const filtered = d.hotels.filter(h => h.nightly <= travelLimits.hotel);
      const box = document.getElementById("hotelBox");
      if (!filtered.length && d.hotels.length) {
        box.innerHTML = `<div class="budget-warn">No lodging within $${travelLimits.hotel}/night budget — raise your limit to see options.</div>`;
        detailCosts.hotelNightly = 0; updateDetailCost(); return;
      }
      const display = filtered.length ? filtered : d.hotels;
      box.innerHTML = display.length ? display.map(h =>
        `<div class="lodge-card"><div class="info"><h4>${h.name}</h4>
          <small>${h.dist_mi!=null?`${h.dist_mi} mi from venue · `:''}${h.rating?`★${h.rating} · `:''}Est. nightly</small></div>
          <div class="price-actions">
            <b>$${h.nightly}/nt</b>
            ${h.lat!=null?`<button class="hotel-map-btn" data-hlat="${h.lat}" data-hlng="${h.lng}" data-flat="${f.lat}" data-flng="${f.lng}" data-hname="${h.name.replace(/"/g,'&quot;')}" onclick="UI.showHotelOnMap(this)">Route ↗ map</button>`:''}
            <a href="${h.booking_url}" target="_blank" rel="noopener">Book ↗</a>
          </div></div>`).join("")
        : '<div class="loading-row">No lodging within this radius — widen the slider.</div>';
      const rates = display.map(h => h.nightly).filter(r => isFinite(r));
      if (rates.length) { detailCosts.hotelNightly = Math.min(...rates); updateDetailCost(); }
    } catch {
      document.getElementById("hotelBox").innerHTML = '<div class="loading-row">Hotels unavailable.</div>';
      detailCosts.hotelNightly = 0; updateDetailCost();
    }
  }
  async function loadCars(f, pickup, nights) {
    const dropoff = addDays(pickup, nights);
    try {
      const d = await API.cars(f.id, pickup, dropoff);
      setTag("carTag", d.live);
      const filtered = d.cars.filter(c => c.daily <= travelLimits.car);
      if (!filtered.length && d.cars.length) {
        document.getElementById("carBox").innerHTML = `<div class="budget-warn">No cars within $${travelLimits.car}/day budget — raise your limit to see options.</div>`;
        detailCosts.carDaily = 0; updateDetailCost(); return;
      }
      const display = filtered.length ? filtered : d.cars;
      document.getElementById("carBox").innerHTML = display.map(c =>
        `<div class="car-card"><div class="info"><h4>${c.car_class}</h4>
          <small>Pick up at ${f.airport} · ${nights} days</small></div>
          <div class="price"><b>$${c.daily}/day</b><a href="${c.booking_url}" target="_blank" rel="noopener">Book ↗</a></div></div>`).join("");
      const dailies = d.cars.map(c => c.daily).filter(r => isFinite(r));
      if (dailies.length) { detailCosts.carDaily = Math.min(...dailies); updateDetailCost(); }
    } catch {
      document.getElementById("carBox").innerHTML = '<div class="loading-row">Cars unavailable.</div>';
      detailCosts.carDaily = 0; updateDetailCost();
    }
  }

  function updateDetailCost() {
    const partyEl = document.getElementById("detailParty");
    if (!partyEl) return;
    const party  = Math.max(1, +partyEl.value || 1);
    const nights = Math.max(1, +(document.getElementById("detailNights")?.value) || 1);
    const rooms  = Math.max(0, +(document.getElementById("detailRooms")?.value) || 0);
    const cars   = Math.max(0, +(document.getElementById("detailCars")?.value)  || 0);

    let total = detailCosts.fee || 0;
    let allLoaded = true;

    if (travelNeeds.flights) {
      if (detailCosts.flightPer !== null) {
        const ft = Math.round((detailCosts.flightPer || 0) * party);
        total += ft;
        document.getElementById("tcFlightLab").textContent =
          detailCosts.flightPer ? `Flights · ${party} person${party!==1?"s":""} × $${Math.round(detailCosts.flightPer)}/ea` : "Flights";
        const el = document.getElementById("tcFlight");
        el.textContent = detailCosts.flightPer ? `$${ft.toLocaleString()}` : "unavailable";
        el.className = "tc-val" + (detailCosts.flightPer ? "" : " tc-pending");
      } else { allLoaded = false; }
    }

    if (travelNeeds.hotel) {
      if (detailCosts.hotelNightly !== null) {
        const ht = Math.round((detailCosts.hotelNightly || 0) * nights * rooms);
        total += ht;
        document.getElementById("tcHotelLab").textContent =
          detailCosts.hotelNightly
            ? `Hotels · ${rooms} rm × ${nights} nt × $${Math.round(detailCosts.hotelNightly)}/nt`
            : "Hotels";
        const el = document.getElementById("tcHotel");
        el.textContent = detailCosts.hotelNightly && rooms > 0 ? `$${ht.toLocaleString()}` : (rooms === 0 ? "—" : "unavailable");
        el.className = "tc-val" + (detailCosts.hotelNightly ? "" : " tc-pending");
      } else { allLoaded = false; }
    }

    if (travelNeeds.car) {
      if (detailCosts.carDaily !== null) {
        const ct = Math.round((detailCosts.carDaily || 0) * nights * cars);
        total += ct;
        document.getElementById("tcCarLab").textContent =
          detailCosts.carDaily && cars > 0
            ? `Cars · ${cars} car${cars!==1?"s":""} × ${nights} days × $${Math.round(detailCosts.carDaily)}/day`
            : "Car rental";
        const el = document.getElementById("tcCar");
        el.textContent = detailCosts.carDaily && cars > 0 ? `$${ct.toLocaleString()}` : (cars === 0 ? "—" : "unavailable");
        el.className = "tc-val" + (detailCosts.carDaily ? "" : " tc-pending");
      } else { allLoaded = false; }
    }

    document.getElementById("tcTotal").textContent =
      allLoaded ? `~$${Math.round(total).toLocaleString()}` : "loading…";
  }
  async function loadRideshare(f, lodgeRad) {
    // Simulate pickup from lodging: offset lodgeRad miles north of venue
    const pickupLat = f.lat + (lodgeRad / 69);
    try {
      const d = await API.rideshare(pickupLat, f.lng, f.id);
      document.getElementById("rideBox").innerHTML = d.estimates.map(e =>
        `<div class="ride-card"><div class="info"><h4>${e.service}
          <span class="ride-badge">${e.distance_mi} mi</span></h4>
          <small>${e.note}</small></div>
          <div class="price"><b>$${e.est_low}–$${e.est_high}</b>
          <a href="${e.deeplink}" target="_blank" rel="noopener">Open ${e.service} ↗</a></div></div>`).join("");
    } catch { document.getElementById("rideBox").innerHTML = '<div class="loading-row">Rideshare unavailable.</div>'; }
  }

  /* ---------- saved list ---------- */
  function getSaved() { return JSON.parse(localStorage.getItem("rr-saved") || "{}"); }
  function isSaved(id) { return String(id) in getSaved(); }
  function _syncChips(containerId, selectedSet) {
    document.querySelectorAll(`#${containerId} .chip`).forEach(el =>
      el.classList.toggle("on", selectedSet.has(el.textContent)));
  }
  function _setSaved(data) {
    localStorage.setItem("rr-saved", JSON.stringify(data));
    const n = Object.keys(data).length;
    document.getElementById("savedCount").textContent = n;
    document.getElementById("savedTabCount").textContent = n;
  }
  function toggleSave(id) {
    const data = getSaved();
    if (String(id) in data) {
      delete data[String(id)];
      _setSaved(data);
      document.querySelectorAll(`.save-btn[data-id="${id}"]`).forEach(b => {
        b.textContent = "☆"; b.classList.remove("saved"); b.title = "Save to list";
      });
    } else {
      const f = results.find(x => x.id === id);
      if (f) { data[String(id)] = f; _setSaved(data); }
      document.querySelectorAll(`.save-btn[data-id="${id}"]`).forEach(b => {
        b.textContent = "★"; b.classList.add("saved"); b.title = "Remove from list";
      });
    }
    if (currentTab === "saved") renderSavedList();
  }
  function showTab(tab) {
    currentTab = tab;
    document.getElementById("tabMatches").classList.toggle("active", tab === "matches");
    document.getElementById("tabSaved").classList.toggle("active", tab === "saved");
    document.getElementById("cardList").style.display = tab === "matches" ? "" : "none";
    document.getElementById("savedList").style.display = tab === "saved" ? "" : "none";
    if (tab === "saved") renderSavedList();
  }
  function openSaved() {
    document.getElementById("detail").classList.remove("open");
    document.getElementById("drawer").classList.add("open");
    showTab("saved");
  }
  function clearSavedList() {
    if (!confirm("Remove all saved festivals?")) return;
    _setSaved({});
    document.querySelectorAll(".save-btn").forEach(b => {
      b.textContent = "☆"; b.classList.remove("saved"); b.title = "Save to list";
    });
    renderSavedList();
  }
  function renderSavedList() {
    const box = document.getElementById("savedList");
    const saved = Object.values(getSaved());
    if (!saved.length) {
      box.innerHTML = '<div class="empty">No saved festivals yet.<br>Hit ☆ on any card to save one.</div>';
      return;
    }
    box.innerHTML = `
      <div class="saved-summary">
        <div>
          <div style="font-size:13px;font-weight:600;color:var(--ink)">${saved.length} festival${saved.length!==1?"s":""} saved</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">Tap a festival to view details · costs load automatically</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px">Est. Grand Total</div>
          <div style="font-family:'JetBrains Mono',monospace;color:var(--amber);font-size:16px" id="savedGrand">—</div>
        </div>
      </div>
      <button class="cost-btn" style="border-color:var(--rose);color:var(--rose);margin-bottom:4px" onclick="UI.clearSavedList()">Clear all saved</button>
      ${saved.map(f => {
        const savedFest = isSaved(f.id);
        return `<div class="saved-item" onclick="UI.openDetail(${f.id})">
          <div class="si-header">
            <div class="si-info">
              <h4>${f.name}</h4>
              <small>${f.city}${f.dist_mi!==undefined?' · '+Math.round(f.dist_mi)+' mi':''}</small>
            </div>
            <button class="save-btn saved" data-id="${f.id}"
              onclick="event.stopPropagation();UI.toggleSave(${f.id})"
              title="Remove from list" style="font-size:18px">★</button>
          </div>
          <div class="si-costs">
            <div class="sc-row"><span class="sc-lab">Submission fee</span><span class="sc-val">$${f.base_fee}</span></div>
            <div class="sc-row"><span class="sc-lab">Flights</span><span class="sc-val sc-loading" id="scf-${f.id}">…</span></div>
            <div class="sc-row"><span class="sc-lab">Hotels</span><span class="sc-val sc-loading" id="sch-${f.id}">…</span></div>
            <div class="sc-row"><span class="sc-lab">Car rental</span><span class="sc-val sc-loading" id="scc-${f.id}">…</span></div>
            <div class="sc-row sc-total"><span class="sc-lab">Est. Total</span><span class="sc-val sc-loading" id="sct-${f.id}">…</span></div>
          </div>
        </div>`;
      }).join("")}`;
    _loadAllSavedCosts(saved);
  }

  async function _loadAllSavedCosts(saved) {
    const party = +document.getElementById("party").value;
    const rooms = Math.ceil(party / 2);
    const defaultNights = +document.getElementById("nights").value;
    const festTotals = {};

    await Promise.all(saved.map(async f => {
      const date = f.festival_start || (f.deadlines||[]).map(d=>d.date).sort()[0] || "2026-09-01";
      const nights = (f.festival_start && f.festival_end)
        ? Math.max(1, Math.ceil((new Date(f.festival_end+"T00:00") - new Date(f.festival_start+"T00:00")) / 86400000))
        : defaultNights;

      let festTotal = f.base_fee || 0;

      const [flRes, htRes, crRes] = await Promise.allSettled([
        API.flights(base.label, f.id, date, f.dist_mi || 500, base.lat, base.lng),
        API.hotels(f.id, 5, date, nights, rooms),
        API.cars(f.id, date, addDays(date, nights)),
      ]);

      const flEl = document.getElementById(`scf-${f.id}`);
      if (flEl) {
        if (flRes.status === "fulfilled" && flRes.value.offers.length) {
          const minPer = Math.min(...flRes.value.offers.map(o => o.price).filter(isFinite));
          if (isFinite(minPer)) {
            const tot = Math.round(minPer * party);
            festTotal += tot;
            flEl.textContent = `$${tot.toLocaleString()} (${party}× $${Math.round(minPer)})`;
            flEl.className = "sc-val";
          } else { flEl.textContent = "—"; flEl.className = "sc-val sc-na"; }
        } else { flEl.textContent = "—"; flEl.className = "sc-val sc-na"; }
      }

      const htEl = document.getElementById(`sch-${f.id}`);
      if (htEl) {
        if (htRes.status === "fulfilled" && htRes.value.hotels.length) {
          const minNt = Math.min(...htRes.value.hotels.map(h => h.nightly).filter(isFinite));
          if (isFinite(minNt)) {
            const tot = Math.round(minNt * nights * rooms);
            festTotal += tot;
            htEl.textContent = `$${tot.toLocaleString()} (${rooms}rm × ${nights}nt)`;
            htEl.className = "sc-val";
          } else { htEl.textContent = "—"; htEl.className = "sc-val sc-na"; }
        } else { htEl.textContent = "—"; htEl.className = "sc-val sc-na"; }
      }

      const crEl = document.getElementById(`scc-${f.id}`);
      if (crEl) {
        if (crRes.status === "fulfilled" && crRes.value.cars.length) {
          const minDay = Math.min(...crRes.value.cars.map(c => c.daily).filter(isFinite));
          if (isFinite(minDay)) {
            const tot = Math.round(minDay * nights);
            festTotal += tot;
            crEl.textContent = `$${tot.toLocaleString()} (${nights} days)`;
            crEl.className = "sc-val";
          } else { crEl.textContent = "—"; crEl.className = "sc-val sc-na"; }
        } else { crEl.textContent = "—"; crEl.className = "sc-val sc-na"; }
      }

      const totEl = document.getElementById(`sct-${f.id}`);
      if (totEl) { totEl.textContent = `~$${festTotal.toLocaleString()}`; totEl.className = "sc-val"; }
      festTotals[f.id] = festTotal;
    }));

    // Grand total across all festivals
    const grand = Object.values(festTotals).reduce((s, v) => s + v, 0);
    const grandEl = document.getElementById("savedGrand");
    if (grandEl) grandEl.textContent = `~$${Math.round(grand).toLocaleString()}`;
  }

  /* ---------- theme / settings ---------- */
  const THEMES = {
    noir:    {"--bg":"#0d0f14","--panel":"#13161e","--panel-2":"#191d27","--line":"#262b38","--amber":"#f4b740","--amber-dim":"#c8902a","--accent-text":"#1a1206","--ink":"#e9eaf0","--muted":"#8a90a2","--faint":"#5a6072","--teal":"#43c6b8","--rose":"#e36a5e"},
    blue:    {"--bg":"#070d1a","--panel":"#0d1426","--panel-2":"#121d33","--line":"#1a2840","--amber":"#4a9eff","--amber-dim":"#2170d9","--accent-text":"#020c1e","--ink":"#dde8ff","--muted":"#7a8faa","--faint":"#4a5f7a","--teal":"#43c6b8","--rose":"#e36a5e"},
    scarlet: {"--bg":"#120808","--panel":"#1c0c0c","--panel-2":"#240f0f","--line":"#3a1515","--amber":"#e05252","--amber-dim":"#b83535","--accent-text":"#2a0808","--ink":"#f0e0e0","--muted":"#9a7070","--faint":"#6a4545","--teal":"#43c6b8","--rose":"#ff8a7a"},
    forest:  {"--bg":"#08100c","--panel":"#0e1a14","--panel-2":"#13231b","--line":"#1c3226","--amber":"#3dc98a","--amber-dim":"#27a06a","--accent-text":"#051a0e","--ink":"#d0f0e0","--muted":"#70997a","--faint":"#456050","--teal":"#4adbc0","--rose":"#e36a5e"},
  };
  const THEME_LABELS = { noir:"Film Noir", blue:"Midnight Blue", scarlet:"Scarlet", forest:"Forest" };

  function _applyVars(vars) {
    Object.entries(vars).forEach(([k,v]) => document.documentElement.style.setProperty(k, v));
  }
  function _darkenHex(hex, pct) {
    const n = parseInt(hex.replace("#",""), 16);
    const r = Math.max(0, Math.round((n>>16)*(1-pct))).toString(16).padStart(2,"0");
    const g = Math.max(0, Math.round(((n>>8)&0xff)*(1-pct))).toString(16).padStart(2,"0");
    const b = Math.max(0, Math.round((n&0xff)*(1-pct))).toString(16).padStart(2,"0");
    return "#"+r+g+b;
  }
  function _luminance(hex) {
    const n = parseInt(hex.replace("#",""), 16);
    return (0.299*(n>>16) + 0.587*((n>>8)&0xff) + 0.114*(n&0xff)) / 255;
  }
  function applyTheme(key) {
    if (!THEMES[key]) return;
    _applyVars(THEMES[key]);
    localStorage.setItem("rr-theme", key);
    localStorage.removeItem("rr-custom-accent");
    document.querySelectorAll(".theme-swatch").forEach(s =>
      s.classList.toggle("active", s.dataset.theme === key));
    document.getElementById("accentPicker").value = THEMES[key]["--amber"];
  }
  function applyCustomAccent() {
    const hex = document.getElementById("accentPicker").value;
    _applyVars({
      "--amber": hex,
      "--amber-dim": _darkenHex(hex, 0.25),
      "--accent-text": _luminance(hex) > 0.5 ? "#1a1206" : "#e9eaf0",
    });
    localStorage.setItem("rr-custom-accent", hex);
    document.querySelectorAll(".theme-swatch").forEach(s => s.classList.remove("active"));
  }
  function buildThemeSwatches() {
    const active = localStorage.getItem("rr-theme") || "noir";
    document.getElementById("themeSwatches").innerHTML = Object.entries(THEMES).map(([key, t]) =>
      `<div class="theme-swatch${key===active?' active':''}" data-theme="${key}" onclick="UI.applyTheme('${key}')">
        <span class="swatch-preview" style="background:${t['--bg']};border-color:${t['--amber']}">
          <span class="swatch-dot" style="background:${t['--amber']}"></span>
        </span>
        <span class="swatch-name">${THEME_LABELS[key]}</span>
      </div>`).join("");
  }
  function loadSavedTheme() {
    const accent = localStorage.getItem("rr-custom-accent");
    const theme = localStorage.getItem("rr-theme");
    if (accent) {
      _applyVars({"--amber":accent,"--amber-dim":_darkenHex(accent,0.25),"--accent-text":_luminance(accent)>0.5?"#1a1206":"#e9eaf0"});
    } else if (theme && THEMES[theme]) {
      _applyVars(THEMES[theme]);
    }
  }
  function openSettings() { document.getElementById("settingsPanel").classList.add("open"); }
  function closeSettings() { document.getElementById("settingsPanel").classList.remove("open"); }

  /* ---------- section resets ---------- */
  function resetFilm() {
    selectedGenres.clear(); selectedGenres.add("Drama");
    selectedLanguages.clear(); selectedLanguages.add("English");
    document.getElementById("runtime").value = 14;
    _syncChips("genreChips", selectedGenres);
    _syncChips("langChips", selectedLanguages);
  }
  function resetSearch() {
    base = { lat: 34.075, lng: -84.294, label: "Alpharetta, GA" };
    document.getElementById("baseSearch").value = base.label;
    document.getElementById("geoStatus").textContent = "";
    document.getElementById("radius").value = 600;
    document.getElementById("radiusVal").textContent = "600 mi";
    document.getElementById("dateFrom").value = "2026-07-01";
    document.getElementById("dateTo").value = "2027-06-30";
  }
  function resetBudget() {
    document.getElementById("festBudget").value = 2500;
    document.getElementById("travelBudget").value = 6000;
    document.getElementById("party").value = 3;
    document.getElementById("nights").value = 3;
    document.getElementById("lodgeRad").value = 5;
    document.getElementById("lodgeRadVal").textContent = "5 mi";
  }
  function resetTravel() {
    document.getElementById("needFlights").checked = true;
    document.getElementById("needHotel").checked   = true;
    document.getElementById("needCar").checked     = true;
    document.getElementById("needRide").checked    = true;
    document.getElementById("maxFlight").value = 800;
    document.getElementById("maxHotel").value  = 200;
    document.getElementById("maxCar").value    = 100;
    onTravelChange();
  }

  /* ---------- travel needs ---------- */
  function onTravelChange() {
    travelNeeds.flights = document.getElementById("needFlights").checked;
    travelNeeds.hotel   = document.getElementById("needHotel").checked;
    travelNeeds.car     = document.getElementById("needCar").checked;
    travelNeeds.ride    = document.getElementById("needRide").checked;
    travelLimits.flight = +document.getElementById("maxFlight").value || Infinity;
    travelLimits.hotel  = +document.getElementById("maxHotel").value  || Infinity;
    travelLimits.car    = +document.getElementById("maxCar").value    || Infinity;
    // Show/hide budget limit inputs next to each toggle
    document.getElementById("limitFlight").style.display = travelNeeds.flights ? "" : "none";
    document.getElementById("limitHotel").style.display  = travelNeeds.hotel   ? "" : "none";
    document.getElementById("limitCar").style.display    = travelNeeds.car     ? "" : "none";
    // If detail panel is open, sync section visibility and recalc total
    if (currentDetailId !== null) {
      ["secFlights","secHotel","secCar","secRide"].forEach((sid, i) => {
        const el = document.getElementById(sid);
        if (el) el.style.display = [travelNeeds.flights, travelNeeds.hotel, travelNeeds.car, travelNeeds.ride][i] ? "" : "none";
      });
      ["tcRowFlight","tcRowHotel","tcRowCar"].forEach((sid, i) => {
        const el = document.getElementById(sid);
        if (el) el.style.display = [travelNeeds.flights, travelNeeds.hotel, travelNeeds.car][i] ? "" : "none";
      });
      // Zero out disabled categories so total can still compute
      if (!travelNeeds.flights && detailCosts.flightPer  === null) detailCosts.flightPer   = 0;
      if (!travelNeeds.hotel   && detailCosts.hotelNightly=== null) detailCosts.hotelNightly= 0;
      if (!travelNeeds.car     && detailCosts.carDaily    === null) detailCosts.carDaily    = 0;
      updateDetailCost();
    }
  }

  /* ---------- hotel map route ---------- */
  function showHotelOnMap(btn) {
    const hotelLat = +btn.dataset.hlat, hotelLng = +btn.dataset.hlng;
    const festLat  = +btn.dataset.flat, festLng  = +btn.dataset.flng;
    const name = btn.dataset.hname;
    clearHotelMap();
    hotelMarker = L.marker([hotelLat, hotelLng], {
      icon: L.divIcon({ className: "", html: '<div class="hotel-pin">H</div>', iconSize: [26, 26], iconAnchor: [13, 13] })
    }).addTo(map).bindPopup(`<b>${name}</b><br><span style="font-size:11px;opacity:.7">Estimated location</span>`).openPopup();
    hotelRouteLine = L.polyline([[hotelLat, hotelLng], [festLat, festLng]], {
      color: "#43c6b8", weight: 2, dashArray: "6 4", opacity: 0.85
    }).addTo(map);
    document.querySelectorAll(".hotel-map-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");

    // Slide the detail panel away so the route is fully visible.
    // Don't call closeDetail() — that would clear the hotel map and lose currentDetailId.
    document.getElementById("detail").classList.remove("open");

    // Wait for the .28s CSS transition, then resize + fit bounds.
    // Pad right for the results drawer (390px) which stays open behind the detail.
    setTimeout(() => {
      map.invalidateSize();
      const drawerOpen = document.getElementById("drawer").classList.contains("open");
      map.fitBounds([[hotelLat, hotelLng], [festLat, festLng]], {
        paddingTopLeft:     [30, 40],
        paddingBottomRight: [drawerOpen ? 410 : 40, 40],
      });
    }, 300);
  }
  function clearHotelMap() {
    if (hotelMarker)    { map.removeLayer(hotelMarker);    hotelMarker    = null; }
    if (hotelRouteLine) { map.removeLayer(hotelRouteLine); hotelRouteLine = null; }
  }

  /* ---------- URL share ---------- */
  function syncToURL() {
    const p = new URLSearchParams();
    p.set("lat", base.lat);
    p.set("lng", base.lng);
    p.set("loc", base.label);
    p.set("r",   document.getElementById("radius").value);
    p.set("g",   [...selectedGenres].join(","));
    p.set("lang",[...selectedLanguages].join(","));
    p.set("rt",  document.getElementById("runtime").value);
    p.set("fee", document.getElementById("festBudget").value);
    p.set("df",  document.getElementById("dateFrom").value);
    p.set("dt",  document.getElementById("dateTo").value);
    history.replaceState(null, "", "#" + p.toString());
  }
  function loadFromURL() {
    const hash = location.hash.slice(1);
    if (!hash) return;
    try {
      const p = new URLSearchParams(hash);
      if (p.get("lat") && p.get("lng")) {
        base = { lat: +p.get("lat"), lng: +p.get("lng"), label: p.get("loc") || "" };
      }
      if (p.get("r"))   { document.getElementById("radius").value = p.get("r"); document.getElementById("radiusVal").textContent = p.get("r") + " mi"; }
      if (p.get("g"))   { selectedGenres.clear();   p.get("g").split(",").filter(Boolean).forEach(g => selectedGenres.add(g)); }
      if (p.get("lang")){ selectedLanguages.clear(); p.get("lang").split(",").filter(Boolean).forEach(l => selectedLanguages.add(l)); }
      if (p.get("rt"))  document.getElementById("runtime").value    = p.get("rt");
      if (p.get("fee")) document.getElementById("festBudget").value  = p.get("fee");
      if (p.get("df"))  document.getElementById("dateFrom").value    = p.get("df");
      if (p.get("dt"))  document.getElementById("dateTo").value      = p.get("dt");
    } catch { /* malformed hash — ignore */ }
  }
  function copyShareLink() {
    syncToURL();
    navigator.clipboard.writeText(location.href).then(() => {
      const btn = document.getElementById("shareBtn");
      if (!btn) return;
      const orig = btn.textContent;
      btn.textContent = "Copied!";
      setTimeout(() => { btn.textContent = orig; }, 1500);
    });
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
  function closeDrawer(){ currentDetailId = null; document.getElementById("drawer").classList.remove("open"); document.getElementById("detail").classList.remove("open"); }
  function closeDetail(){ currentDetailId = null; clearHotelMap(); document.getElementById("detail").classList.remove("open"); }
  function resetView(){ map.setView([39.5,-98.35],4); setTimeout(()=>map.invalidateSize(),50); }

  /* ---------- sidebar collapse + accordion ---------- */
  function toggleSidebar() {
    if (window.innerWidth <= 640) {
      // Mobile: toggle bottom-sheet
      const ctrl = document.querySelector(".controls");
      const overlay = document.getElementById("mobileOverlay");
      const open = ctrl.classList.toggle("mobile-open");
      if (overlay) overlay.style.display = open ? "" : "none";
      return;
    }
    // Desktop: slide sidebar in/out
    const app = document.querySelector(".app");
    const closing = !app.classList.contains("sidebar-closed");
    app.classList.toggle("sidebar-closed");
    const btn = document.getElementById("sidebarReopenBtn");
    if (btn) btn.style.display = closing ? "" : "none";
    setTimeout(() => map.invalidateSize(), 300);
  }
  function initAccordions() {
    document.querySelectorAll(".controls .group").forEach(group => {
      const legend = group.querySelector(".legend");
      if (!legend) return;
      legend.addEventListener("click", e => {
        if (e.target.closest(".reset-btn")) return;
        group.classList.toggle("grp-closed");
      });
    });
  }

  /* ---------- boot ---------- */
  async function boot() {
    loadSavedTheme();
    initMap();
    loadFromURL();          // restore state BEFORE buildControls so chips render correctly
    buildControls();
    if (base.label) document.getElementById("baseSearch").value = base.label;
    wireGeocode();
    buildThemeSwatches();
    initAccordions();
    _setSaved(getSaved()); // sync saved count on load
    try {
      const h = await API.health();
      document.getElementById("modeFlag").textContent = h.live_scraping ? "LIVE" : "ESTIMATE";
    } catch {
      document.getElementById("modeFlag").textContent = "OFFLINE";
    }
    runSearch();
  }

  return { boot, runSearch, openDetail, openDrawer, closeDrawer, closeDetail, resetView,
           showTab, openSaved, toggleSave, clearSavedList,
           applyTheme, applyCustomAccent, openSettings, closeSettings,
           resetFilm, resetSearch, resetBudget, resetTravel,
           updateDetailCost, onTravelChange, showHotelOnMap, toggleSidebar,
           copyShareLink };
})();

window.addEventListener("load", UI.boot);
