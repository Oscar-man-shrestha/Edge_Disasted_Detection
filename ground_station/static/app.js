/* Ground station dashboard. Vanilla JS, no build step, no network beyond this server.
   Data: GET /api/state on load and on every stream (re)connect; live updates via SSE. */
(function () {
  "use strict";

  var PRIORITY = { person: 1, fire: 2, smoke: 3 };
  var TYPES = ["person", "fire", "smoke"];
  var LETTER = { person: "P", fire: "F", smoke: "S" };
  var LINK_LOST_S = 3, PREVIEW_STALE_S = 5, SPARK_N = 60;

  var S = {
    offset: 0,            // server_time - local time (s)
    mission: null, missions: [],
    telemetry: null, telemetryAt: null,
    preview: null,
    alerts: new Map(),
    track: [],
    selected: null,
    linkState: "never",
    spark: { fps: [], pow: [] },
    seen: new Set(),       // alert ids already notified
  };
  var prefs = loadPrefs();

  // ------------------------------------------------------------------ utils
  function $(id) { return document.getElementById(id); }
  function nowS() { return Date.now() / 1000 + S.offset; }
  function syncClock(serverTime) { if (typeof serverTime === "number") S.offset = serverTime - Date.now() / 1000; }
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    });
    (kids || []).forEach(function (c) { if (c != null) el.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return el;
  }
  function num(v, d) { return typeof v === "number" && isFinite(v) ? v.toFixed(d == null ? 0 : d) : "—"; }
  function fmtDur(s) {
    s = Math.max(0, Math.floor(s));
    var hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60;
    return [hh, mm, ss].map(function (x) { return String(x).padStart(2, "0"); }).join(":");
  }
  function timePart(w) { return w ? String(w).split(" ").pop() : "—"; }
  function api(path, opts) {
    opts = opts || {};
    if (opts.json !== undefined) {
      opts.method = opts.method || "POST";
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(opts.json);
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) throw new Error(path + " → HTTP " + r.status);
      return r.json();
    });
  }
  function loadPrefs() {
    var d = { mute: false, follow: true, types: TYPES.slice(), status: "open" };
    try { var p = JSON.parse(localStorage.getItem("gs-prefs") || "{}"); return Object.assign(d, p); }
    catch (e) { return d; }
  }
  function savePrefs() { try { localStorage.setItem("gs-prefs", JSON.stringify(prefs)); } catch (e) { /* private mode */ } }
  function parseLocal(ts) {   // "YYYY-MM-DD HH:MM:SS" (station local time)
    if (!ts) return null;
    var d = new Date(String(ts).replace(" ", "T"));
    return isNaN(d) ? null : d.getTime() / 1000;
  }

  // ------------------------------------------------------------------ map
  var map = L.map("map", { zoomControl: true, attributionControl: true, worldCopyJump: true })
    .setView([12.9715, 77.5905], 16);
  L.tileLayer("/tiles/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap contributors (cached offline)",
  }).addTo(map);
  var trail = L.polyline([], { color: "#e8ebf1", weight: 2.5, opacity: 0.7, dashArray: "6 6" }).addTo(map);
  var alertLayer = L.layerGroup().addTo(map);
  var markers = new Map();
  var droneMarker = null, fitted = false;

  function droneIcon(course, stale) {
    var svg = '<svg width="30" height="30" viewBox="0 0 30 30" style="transform:rotate(' + (course || 0) + 'deg)">' +
      '<path d="M15 2 L26 27 L15 21 L4 27 Z" fill="#e8ebf1" stroke="#0d1016" stroke-width="2" stroke-linejoin="round"/></svg>';
    return L.divIcon({ className: "", html: '<div class="drone-icon' + (stale ? " stale" : "") + '">' + svg + "</div>",
      iconSize: [34, 34], iconAnchor: [17, 17] });
  }
  function alertIcon(a) {
    var cls = "amark " + a.type + " " + a.status + (S.selected === a.id ? " selected" : "");
    return L.divIcon({ className: "", html: '<div class="' + cls + '">' + LETTER[a.type] + "</div>",
      iconSize: [26, 26], iconAnchor: [13, 13] });
  }
  function located(a) { return a.lat != null && a.lon != null; }
  function upsertMarker(a) {
    var m = markers.get(a.id);
    if (!located(a) || !visible(a)) { if (m) { alertLayer.removeLayer(m); markers.delete(a.id); } return; }
    if (!m) {
      m = L.marker([a.lat, a.lon], { icon: alertIcon(a), riseOnHover: true, keyboard: true,
        title: a.type + " " + Math.round(a.conf * 100) + "%" });
      m.on("click", function () { select(a.id, true); });
      m.addTo(alertLayer);
      markers.set(a.id, m);
    } else {
      m.setIcon(alertIcon(a));
    }
    m.setZIndexOffset(a.status === "new" ? 1000 : 0);
  }
  function renderDrone() {
    var t = S.telemetry, g = t && t.gps;
    var stale = S.linkState !== "live";
    if (g && g.fix === true && typeof g.lat === "number") {
      var ll = [g.lat, g.lon];
      if (!droneMarker) droneMarker = L.marker(ll, { icon: droneIcon(g.course_deg, stale), zIndexOffset: 2000, keyboard: false }).addTo(map);
      else { droneMarker.setLatLng(ll); droneMarker.setIcon(droneIcon(g.course_deg, stale)); }
      if (prefs.follow && !stale) map.panTo(ll, { animate: true, duration: 0.5 });
      if (!fitted) { map.setView(ll, 17); fitted = true; }
    } else if (droneMarker) {
      droneMarker.setIcon(droneIcon(g && g.course_deg, true));   // last known, faded
    }
  }
  function addTrackPoint(lat, lon) {
    var pts = trail.getLatLngs(), last = pts[pts.length - 1];
    if (!last || map.distance(last, [lat, lon]) >= 2) trail.addLatLng([lat, lon]);
  }
  function fitAll() {
    var b = L.latLngBounds([]);
    trail.getLatLngs().forEach(function (p) { b.extend(p); });
    S.alerts.forEach(function (a) { if (located(a)) b.extend([a.lat, a.lon]); });
    if (droneMarker) b.extend(droneMarker.getLatLng());
    if (b.isValid()) map.fitBounds(b, { padding: [40, 40], maxZoom: 18 });
  }

  // ------------------------------------------------------------------ top bar
  function renderLink() {
    var pill = $("linkPill"), age = S.telemetryAt == null ? null : nowS() - S.telemetryAt;
    var st = age == null ? "never" : (age < LINK_LOST_S ? "live" : "lost");
    if (st !== S.linkState) { S.linkState = st; renderDrone(); }
    pill.className = "pill link-pill " + st;
    var id = S.telemetry && S.telemetry.drone_id ? " · " + S.telemetry.drone_id : "";
    $("linkText").textContent = st === "live" ? "LIVE" + id : st === "lost" ? "LINK LOST · " + Math.round(age) + " s" : "WAITING FOR DRONE";
  }
  function renderGps() {
    var g = S.telemetry && S.telemetry.gps, chip = $("gpsChip");
    if (!g) { chip.textContent = "GPS —"; chip.className = "chip"; return; }
    if (g.fix === true) {
      var parts = [g.mode === "sim" ? "SIM GPS" : "FIX"];
      if (g.sats != null) parts.push(g.sats + " sats");
      if (g.hdop != null) parts.push("HDOP " + num(g.hdop, 1));
      chip.textContent = parts.join(" · "); chip.className = "chip ok";
    } else { chip.textContent = "NO FIX" + (g.sats != null ? " · " + g.sats + " sats" : ""); chip.className = "chip bad"; }
  }
  function renderMission() {
    var m = S.mission;
    $("missionName").textContent = m ? m.name : "—";
    if (m) {
      var base = "/api/missions/" + m.id + "/export.";
      $("exCsv").href = base + "csv"; $("exGeo").href = base + "geojson"; $("exKml").href = base + "kml";
      $("exReport").href = "/report/" + m.id;
    }
  }
  function renderTimer() {
    var start = S.mission && parseLocal(S.mission.started_at);
    $("missionTimer").textContent = start ? fmtDur(Date.now() / 1000 - start) : "00:00:00";
  }
  function renderCounters() {
    var box = $("counters"); box.textContent = "";
    var openNew = 0;
    TYPES.forEach(function (t) {
      var total = 0, fresh = 0;
      S.alerts.forEach(function (a) { if (a.type === t) { total++; if (a.status === "new") fresh++; } });
      openNew += fresh;
      box.appendChild(h("span", { class: "counter" + (fresh ? " hot" : ""), title: t + ": " + fresh + " new of " + total },
        [h("i", { style: "background:var(--" + t + ")" }), t + " ", h("b", { text: fresh + "/" + total })]));
    });
    document.title = (openNew ? "(" + openNew + ") New alerts · " : "") + "Ground Station";
  }

  // ------------------------------------------------------------------ live panel
  function card(k, v, unit, cls) {
    return h("div", { class: "card" + (cls ? " " + cls : "") }, [
      h("div", { class: "k", text: k }), h("div", { class: "v" }, [v, unit ? h("small", { text: " " + unit }) : null])]);
  }
  function tempClass(c) { return typeof c !== "number" ? "" : c >= 80 ? "crit" : c >= 70 ? "warn" : ""; }
  function renderCards() {
    var t = S.telemetry || {}, p = t.pipeline || {}, s = t.system || {}, l = t.link || {};
    var box = $("cards"); box.textContent = "";
    var stateEl = h("span", {}, [h("span", { class: "state-dot " + (p.state || "") }), (p.state || "—").toUpperCase()]);
    box.appendChild(card("Pipeline", stateEl));
    box.appendChild(card("Frame rate", num(p.fps, 1), "fps"));
    box.appendChild(card("Stage 1", num(p.stage1_ms, 1), "ms"));
    box.appendChild(card("Stage 2 (YOLO)", num(p.stage2_ms, 0), "ms"));
    box.appendChild(card("YOLO runs", (p.stage2_runs == null ? "—" : String(p.stage2_runs)),
      p.stage2_skipped ? p.stage2_skipped + " skipped" : ""));
    box.appendChild(card("Board power", s.power_mw == null ? "—" : num(s.power_mw / 1000, 1), "W"));
    box.appendChild(card("CPU temp", num(s.cpu_temp_c, 0), "°C", tempClass(s.cpu_temp_c)));
    box.appendChild(card("GPU temp", num(s.gpu_temp_c, 0), "°C", tempClass(s.gpu_temp_c)));
    box.appendChild(card("CPU / GPU load", num(s.cpu_load_pct, 0) + " / " + num(s.gpu_load_pct, 0), "%"));
    box.appendChild(card("Memory", s.ram_used_mb == null ? "—" : (s.ram_used_mb / 1024).toFixed(1),
      s.ram_total_mb ? "of " + (s.ram_total_mb / 1024).toFixed(1) + " GB" : ""));
    box.appendChild(card("Alerts waiting", l.alerts_buffered == null ? "—" : String(l.alerts_buffered), "on drone",
      l.alerts_buffered ? "warn" : ""));
    var g = t.gps || {};
    box.appendChild(card("Speed / heading", num(g.speed_mps, 1) + " m/s", g.course_deg == null ? "" : num(g.course_deg, 0) + "°"));
    $("fpsNow").textContent = num(p.fps, 1) + " fps";
    $("powNow").textContent = s.power_mw == null ? "—" : num(s.power_mw / 1000, 1) + " W";
  }
  function pushSpark() {
    var t = S.telemetry || {};
    var fps = t.pipeline && t.pipeline.fps, pw = t.system && t.system.power_mw;
    S.spark.fps.push(typeof fps === "number" ? fps : null);
    S.spark.pow.push(typeof pw === "number" ? pw / 1000 : null);
    ["fps", "pow"].forEach(function (k) { if (S.spark[k].length > SPARK_N) S.spark[k].shift(); });
    drawSpark($("sparkFps"), S.spark.fps); drawSpark($("sparkPow"), S.spark.pow);
  }
  function drawSpark(cv, data, hoverIdx) {
    var dpr = window.devicePixelRatio || 1, w = cv.clientWidth, hgt = cv.clientHeight;
    if (!w) return;
    cv.width = w * dpr; cv.height = hgt * dpr;
    var ctx = cv.getContext("2d"); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, hgt);
    var vals = data.filter(function (v) { return v != null; });
    ctx.strokeStyle = "#2a3140"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, hgt - 0.5); ctx.lineTo(w, hgt - 0.5); ctx.stroke();       // recessive baseline
    if (vals.length < 2) return;
    var max = Math.max.apply(null, vals) * 1.15 || 1, min = 0;
    var x = function (i) { return (i + SPARK_N - data.length) / (SPARK_N - 1) * (w - 4) + 2; };
    var y = function (v) { return hgt - 3 - (v - min) / (max - min) * (hgt - 8); };
    ctx.strokeStyle = "#3987e5"; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath();
    var started = false;
    data.forEach(function (v, i) {
      if (v == null) { started = false; return; }
      if (!started) { ctx.moveTo(x(i), y(v)); started = true; } else ctx.lineTo(x(i), y(v));
    });
    ctx.stroke();
    if (hoverIdx != null && data[hoverIdx] != null) {
      ctx.strokeStyle = "#7a8293"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x(hoverIdx), 0); ctx.lineTo(x(hoverIdx), hgt); ctx.stroke();
      ctx.fillStyle = "#3987e5"; ctx.strokeStyle = "#1b202b"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x(hoverIdx), y(data[hoverIdx]), 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }
  }
  function wireSparkHover(cv, key, unit, digits) {
    var tip = $("sparkTip");
    cv.addEventListener("mousemove", function (e) {
      var data = S.spark[key], r = cv.getBoundingClientRect();
      if (data.length < 2) return;
      var slot = Math.round((e.clientX - r.left - 2) / (r.width - 4) * (SPARK_N - 1));
      var idx = Math.min(data.length - 1, Math.max(0, slot - (SPARK_N - data.length)));
      drawSpark(cv, data, idx);
      var v = data[idx], ago = data.length - 1 - idx;
      tip.hidden = false;
      tip.textContent = (v == null ? "no data" : v.toFixed(digits) + " " + unit) + " · " + (ago ? ago + " s ago" : "now");
      var pr = cv.parentNode.parentNode.getBoundingClientRect();
      tip.style.left = (e.clientX - pr.left) + "px"; tip.style.top = (r.top - pr.top) + "px";
    });
    cv.addEventListener("mouseleave", function () { tip.hidden = true; drawSpark(cv, S.spark[key]); });
  }
  function renderPreview() {
    var p = S.preview, img = $("previewImg");
    if (!p) { $("previewEmpty").hidden = false; $("yoloBadge").hidden = true; $("staleOverlay").hidden = true; return; }
    var src = "/api/preview.jpg?t=" + p.t;
    if (img.getAttribute("data-t") !== String(p.t)) {
      var next = new Image();
      next.onload = function () { img.src = src; img.setAttribute("data-t", String(p.t)); $("previewEmpty").hidden = true; };
      next.src = src;
    }
    $("yoloBadge").hidden = !p.stage2;
    renderPreviewAge();
  }
  function renderPreviewAge() {
    var p = S.preview;
    if (!p) { $("previewAge").textContent = "no image yet"; return; }
    var age = nowS() - p.t;
    $("previewAge").textContent = age < 1.5 ? "live" : Math.round(age) + " s ago";
    $("staleOverlay").hidden = age < PREVIEW_STALE_S;
  }

  // ------------------------------------------------------------------ alert feed
  function visible(a) {
    if (prefs.types.indexOf(a.type) < 0) return false;
    if (prefs.status === "all") return true;
    if (prefs.status === "open") return a.status !== "resolved";
    return a.status === prefs.status;
  }
  function sortedAlerts() {
    return Array.from(S.alerts.values()).sort(function (a, b) {
      var sa = a.status === "resolved" ? 1 : 0, sb = b.status === "resolved" ? 1 : 0;
      return sa - sb || PRIORITY[a.type] - PRIORITY[b.type] || b.id - a.id;
    });
  }
  function coords(a) { return a.lat.toFixed(6) + ", " + a.lon.toFixed(6); }
  function alertCard(a, flash) {
    var thumb = a.snapshot
      ? h("button", { class: "thumb", style: "background-image:url('/snap/" + encodeURIComponent(a.snapshot) + "')",
          "aria-label": "Open snapshot of alert " + a.id, onclick: function () { openLightbox(a); } })
      : h("div", { class: "thumb none", text: "no image" });
    var where = located(a) ? h("span", { text: coords(a) }) : h("span", { class: "nofix", text: "no GPS fix" });
    var acts = [];
    if (a.status === "new") acts.push(h("button", { class: "btn primary", text: "Acknowledge", onclick: function () { setStatus(a.id, "acknowledged"); } }));
    if (a.status !== "resolved") acts.push(h("button", { class: "btn", text: "Resolve", onclick: function () { setStatus(a.id, "resolved"); } }));
    else acts.push(h("button", { class: "btn ghost", text: "Reopen", onclick: function () { setStatus(a.id, "acknowledged"); } }));
    acts.push(h("button", { class: "btn ghost", text: a.note ? "Edit note" : "Note", onclick: function () { editNote(a); } }));
    if (located(a)) {
      acts.push(h("button", { class: "btn ghost", text: "Copy", title: "Copy coordinates",
        onclick: function (e) { copyText(coords(a), e.target); } }));
      acts.push(h("a", { class: "btn ghost", text: "Maps ↗", target: "_blank", rel: "noopener",
        title: "Open in Google Maps (needs internet)", href: "https://www.google.com/maps?q=" + a.lat + "," + a.lon }));
    }
    var li = h("li", { class: "acard " + a.type + " " + a.status + (S.selected === a.id ? " selected" : "") + (flash ? " flash" : ""),
      "data-id": a.id }, [
      thumb,
      h("div", {}, [
        h("div", { class: "arow" }, [
          h("span", { class: "tbadge " + a.type, text: a.type }),
          h("b", { text: Math.round(a.conf * 100) + "%" }),
          h("span", { class: "sbadge " + a.status, text: a.status }),
          h("span", { class: "muted small", text: "#" + a.id }),
        ]),
        h("div", { class: "ameta" }, [timePart(a.wall_time), " · ", where]),
        a.note ? h("div", { class: "anote", text: a.note }) : null,
        h("div", { class: "actions" }, acts),
      ]),
    ]);
    li.addEventListener("click", function (e) {
      if (e.target.closest("button, a")) return;
      select(a.id, false);
    });
    return li;
  }
  function renderFeed(flashId) {
    var list = $("alertList"), shown = 0;
    list.textContent = "";
    sortedAlerts().forEach(function (a) {
      upsertMarker(a);
      if (!visible(a)) return;
      list.appendChild(alertCard(a, a.id === flashId));
      shown++;
    });
    $("feedEmpty").hidden = shown > 0;
    $("feedEmpty").textContent = S.alerts.size ? "No alerts match these filters." :
      "No alerts yet. They appear here the moment the drone detects something.";
    $("feedCount").textContent = shown + " shown · " + S.alerts.size + " total";
    renderCounters();
  }
  function select(id, scroll) {
    var prev = S.selected; S.selected = id;
    [prev, id].forEach(function (x) { var a = S.alerts.get(x); if (a) upsertMarker(a); });
    document.querySelectorAll(".acard.selected").forEach(function (el) { el.classList.remove("selected"); });
    var el = document.querySelector('.acard[data-id="' + id + '"]');
    if (el) { el.classList.add("selected"); if (scroll) el.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
    var a = S.alerts.get(id);
    if (a && located(a) && !scroll) map.panTo([a.lat, a.lon]);
  }
  function setStatus(id, status) {
    api("/api/alerts/" + id, { json: { status: status } }).then(function (r) { applyAlert(r.alert); })
      .catch(function (e) { toast("Could not update alert", e.message); });
  }
  function editNote(a) {
    var dlg = $("noteDialog");
    $("noteTitle").textContent = "Note for " + a.type + " #" + a.id;
    $("noteText").value = a.note || "";
    dlg.returnValue = "";
    dlg.onclose = function () {
      if (dlg.returnValue !== "save") return;
      api("/api/alerts/" + a.id, { json: { note: $("noteText").value } }).then(function (r) { applyAlert(r.alert); })
        .catch(function (e) { toast("Could not save note", e.message); });
    };
    if (dlg.showModal) dlg.showModal(); else { var v = prompt("Note", a.note || ""); if (v != null) { $("noteText").value = v; dlg.returnValue = "save"; dlg.onclose(); } }
  }
  function copyText(t, btn) {
    var done = function () { var o = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.textContent = o; }, 1200); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(done, function () { prompt("Copy:", t); });
    else prompt("Copy coordinates:", t);
  }
  function openLightbox(a) {
    $("lightboxImg").src = "/snap/" + encodeURIComponent(a.snapshot);
    $("lightboxImg").alt = a.type + " alert " + a.id;
    $("lightboxCap").textContent = a.type + " · " + Math.round(a.conf * 100) + "% · " + (a.wall_time || "") +
      (located(a) ? " · " + coords(a) : " · no GPS fix");
    $("lightbox").hidden = false;
    $("lightboxClose").focus();
  }
  function closeLightbox() { $("lightbox").hidden = true; }
  function applyAlert(a) {
    var isNew = !S.alerts.has(a.id);
    S.alerts.set(a.id, a);
    renderFeed(isNew ? a.id : null);
    return isNew;
  }

  // ------------------------------------------------------------------ notifications
  var audio = null;
  function tone(freqs) {
    if (prefs.mute) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === "suspended") audio.resume();
      var t = audio.currentTime;
      freqs.forEach(function (f, i) {
        var o = audio.createOscillator(), g = audio.createGain();
        o.type = "sine"; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t + i * 0.18);
        g.gain.exponentialRampToValueAtTime(0.25, t + i * 0.18 + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.18 + 0.16);
        o.connect(g).connect(audio.destination);
        o.start(t + i * 0.18); o.stop(t + i * 0.18 + 0.17);
      });
    } catch (e) { /* audio unavailable */ }
  }
  function toast(title, body, type, onclick) {
    var el = h("div", { class: "toast " + (type || ""), role: "alert" }, [h("b", { text: title }), body ? h("span", { text: body }) : null]);
    el.addEventListener("click", function () { el.remove(); if (onclick) onclick(); });
    $("toasts").appendChild(el);
    setTimeout(function () { el.remove(); }, 8000);
  }
  function notifyAlert(a) {
    if (S.seen.has(a.id)) return;
    S.seen.add(a.id);
    tone(a.type === "person" ? [880, 660] : [520]);
    toast("New " + a.type + " alert · " + Math.round(a.conf * 100) + "%",
      (located(a) ? coords(a) : "no GPS fix") + " · " + timePart(a.wall_time), a.type,
      function () { select(a.id, true); if (located(a)) map.setView([a.lat, a.lon], Math.max(map.getZoom(), 17)); });
  }

  // ------------------------------------------------------------------ state + stream
  function applyTelemetry(t, serverTime) {
    S.telemetry = t; S.telemetryAt = serverTime;
    var g = t && t.gps;
    if (g && g.fix === true && typeof g.lat === "number") addTrackPoint(g.lat, g.lon);
    renderLink(); renderGps(); renderCards(); renderDrone();
  }
  function loadState() {
    return api("/api/state").then(function (st) {
      syncClock(st.server_time);
      S.mission = st.mission; S.missions = st.missions || [];
      S.alerts = new Map();
      (st.alerts || []).forEach(function (a) { S.alerts.set(a.id, a); S.seen.add(a.id); });
      trail.setLatLngs((st.track || []).map(function (p) { return [p.lat, p.lon]; }));
      S.telemetry = st.telemetry;
      S.telemetryAt = st.link && st.link.age_s != null ? st.server_time - st.link.age_s : null;
      S.preview = st.preview;
      markers.forEach(function (m) { alertLayer.removeLayer(m); }); markers.clear();
      renderMission(); renderTimer(); renderLink(); renderGps(); renderCards(); renderDrone(); renderPreview(); renderFeed();
      if (!fitted && (trail.getLatLngs().length || S.alerts.size)) { fitAll(); fitted = true; }
    }).catch(function (e) { toast("Station unreachable", e.message); });
  }
  var es = null;
  function connectStream() {
    if (es) es.close();
    es = new EventSource("/api/stream");
    es.addEventListener("open", loadState);                     // resync after every (re)connect
    es.addEventListener("hello", function (e) { syncClock(JSON.parse(e.data).server_time); });
    es.addEventListener("telemetry", function (e) {
      var d = JSON.parse(e.data); syncClock(d.server_time); applyTelemetry(d.telemetry, d.server_time);
    });
    es.addEventListener("preview", function (e) {
      var d = JSON.parse(e.data); S.preview = { t: d.t, stage2: d.stage2 }; renderPreview();
    });
    es.addEventListener("alert", function (e) {
      var a = JSON.parse(e.data).alert;
      if (S.mission && a.mission_id !== S.mission.id) return;
      applyAlert(a); notifyAlert(a);
    });
    es.addEventListener("alert_update", function (e) { var a = JSON.parse(e.data).alert; if (S.alerts.has(a.id)) applyAlert(a); });
    es.addEventListener("mission", function () { fitted = false; trail.setLatLngs([]); loadState(); });
    es.addEventListener("link", function (e) { syncClock(JSON.parse(e.data).server_time); renderLink(); });
  }

  // ------------------------------------------------------------------ controls
  function wireControls() {
    var soundBtn = $("soundBtn");
    function paintSound() { soundBtn.setAttribute("aria-pressed", String(!prefs.mute)); soundBtn.textContent = prefs.mute ? "🔕 Muted" : "🔔 Sound on"; }
    soundBtn.addEventListener("click", function () {
      prefs.mute = !prefs.mute; savePrefs(); paintSound();
      if (!prefs.mute) tone([660]);                               // also unlocks audio (user gesture)
    });
    paintSound();
    var followBtn = $("followBtn");
    function paintFollow() { followBtn.setAttribute("aria-pressed", String(prefs.follow)); }
    followBtn.addEventListener("click", function () { prefs.follow = !prefs.follow; savePrefs(); paintFollow(); renderDrone(); });
    map.on("dragstart", function () { if (prefs.follow) { prefs.follow = false; savePrefs(); paintFollow(); } });
    paintFollow();
    $("fitBtn").addEventListener("click", fitAll);
    document.querySelectorAll("#typeFilter button").forEach(function (b) {
      var t = b.getAttribute("data-type");
      b.setAttribute("aria-pressed", String(prefs.types.indexOf(t) >= 0));
      b.addEventListener("click", function () {
        var on = prefs.types.indexOf(t) >= 0;
        prefs.types = on ? prefs.types.filter(function (x) { return x !== t; }) : prefs.types.concat([t]);
        b.setAttribute("aria-pressed", String(!on)); savePrefs(); renderFeed();
      });
    });
    var sf = $("statusFilter"); sf.value = prefs.status;
    sf.addEventListener("change", function () { prefs.status = sf.value; savePrefs(); renderFeed(); });
    $("newMissionBtn").addEventListener("click", function () {
      var name = prompt("Name for the new mission (the current one will be closed):", "");
      if (name === null) return;
      api("/api/missions", { json: { name: name } }).then(function (r) { toast("Mission started", r.mission.name); })
        .catch(function (e) { toast("Could not start mission", e.message); });
    });
    document.querySelectorAll("#exportMenu a").forEach(function (a) {
      a.addEventListener("click", function () { $("exportMenu").open = false; });
    });
    document.addEventListener("click", function (e) { if (!e.target.closest("#exportMenu")) $("exportMenu").open = false; });
    $("lightbox").addEventListener("click", function (e) { if (e.target === $("lightbox")) closeLightbox(); });
    $("lightboxClose").addEventListener("click", closeLightbox);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeLightbox(); });
    wireSparkHover($("sparkFps"), "fps", "fps", 1);
    wireSparkHover($("sparkPow"), "pow", "W", 1);
    window.addEventListener("resize", function () { drawSpark($("sparkFps"), S.spark.fps); drawSpark($("sparkPow"), S.spark.pow); });
  }

  // ------------------------------------------------------------------ boot
  wireControls();
  renderCards();
  loadState();
  connectStream();
  setInterval(function () { renderLink(); renderTimer(); renderPreviewAge(); pushSpark(); }, 1000);
})();
