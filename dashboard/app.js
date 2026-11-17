/* Subsurface ocean temperature dashboard. All numbers come from dashboard/data/*, exported by
   scripts/09_export_dashboard.py from the project's result files. No external JS libraries. */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (tag, attrs = {}, html = "") => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (html) e.innerHTML = html; return e; };
const fmt = (x, d = 2) => (x == null || !isFinite(x) ? "–" : Number(x).toFixed(d));
const fmtInt = (x) => Number(x).toLocaleString("en-US");
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const DPR = Math.min(window.devicePixelRatio || 1, 2);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayLabel = (d) => { const [y, m, dd] = d.split("-"); return `${+dd} ${MONTHS[+m - 1]} ${y}`; };

/* ------------------------------------------------------------------ colour maps */
const CMAPS = {
  thermal: ["#04223b", "#1d3591", "#5a3d97", "#8e4b8f", "#c25c78", "#ec7558", "#fb9e3f", "#f3d14b", "#e8fa5b"],
  balance: ["#1b2f6e", "#3a6fb5", "#a9c9e6", "#f3efe8", "#f0b39a", "#c9502f", "#6b1620"],
  heat: ["#f6efd8", "#f2d48a", "#e9a04c", "#d4622b", "#a5291f", "#5c0f1a"],
  deep: ["#fdfecc", "#a5dfab", "#5fb6a5", "#3a85a2", "#3a538e", "#2f2a5a", "#1c1225"],
};
const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const LUT = {};
for (const [k, stops] of Object.entries(CMAPS)) {
  const c = stops.map(hex), lut = new Uint8Array(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = (i / 255) * (c.length - 1), j = Math.min(Math.floor(t), c.length - 2), f = t - j;
    for (let q = 0; q < 3; q++) lut[i * 3 + q] = Math.round(c[j][q] + (c[j + 1][q] - c[j][q]) * f);
  }
  LUT[k] = lut;
}
const cmapCss = (k) => `linear-gradient(90deg, ${CMAPS[k].join(",")})`;
const cmapCssV = (k) => `linear-gradient(0deg, ${CMAPS[k].join(",")})`;

/* ------------------------------------------------------------------ data */
let META, S, N, CELLIDX;
const dayCache = new Map(), climCache = new Map();
async function getDay(day) {
  if (!dayCache.has(day)) dayCache.set(day, fetch(`data/day_${day.replace(/-/g, "")}.bin`).then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); }).then((b) => new Int16Array(b)));
  return dayCache.get(day);
}
async function getClim(month) {
  const k = String(month).padStart(2, "0");
  if (!climCache.has(k)) climCache.set(k, fetch(`data/clim_${k}.bin`).then((r) => r.arrayBuffer()).then((b) => new Int16Array(b)));
  return climCache.get(k);
}
const MISS = -32768;
const val = (arr, row, i, scale) => { const v = arr[row * N + i]; return v === MISS ? NaN : v / scale; };

/* ------------------------------------------------------------------ small SVG chart helper */
function scaleLin(d0, d1, r0, r1) { return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0); }
function scaleSqrt(d0, d1, r0, r1) { return (v) => r0 + ((Math.sqrt(Math.max(v, 0)) - Math.sqrt(d0)) / (Math.sqrt(d1) - Math.sqrt(d0))) * (r1 - r0); }
const DEPTH_TICKS = [0, 50, 100, 200, 300, 500, 1000];

function chart(host, o) {
  const W = o.w || 520, H = o.h || 360, m = Object.assign({ l: 48, r: 14, t: 14, b: 40 }, o.m || {});
  const X = (o.x.sqrt ? scaleSqrt : scaleLin)(o.x.min, o.x.max, m.l, W - m.r);
  const Y = (o.y.sqrt ? scaleSqrt : scaleLin)(o.y.min, o.y.max, o.y.invert ? m.t : H - m.b, o.y.invert ? H - m.b : m.t);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${o.label || "chart"}">`;
  (o.bands || []).forEach((b, bi) => {
    if (b.y) s += `<rect x="${m.l}" y="${Y(b.y[0])}" width="${W - m.l - m.r}" height="${Y(b.y[1]) - Y(b.y[0])}" fill="${b.fill}"/>` + (b.text ? `<text x="${m.l + 6}" y="${Y(b.y[0]) + 13}" class="lab">${b.text}</text>` : "");
    if (b.x) s += `<rect x="${X(b.x[0])}" y="${m.t}" width="${Math.max(2, X(b.x[1]) - X(b.x[0]))}" height="${H - m.t - m.b}" fill="${b.fill}"/>` + (b.text ? `<text x="${X(b.x[0]) + 3}" y="${m.t + 11 + bi * 13}" class="lab">${b.text}</text>` : "");
  });
  s += `<g class="grid">`;
  for (const t of o.y.ticks) s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}"/>`;
  for (const t of o.x.ticks) s += `<line y1="${m.t}" y2="${H - m.b}" x1="${X(t)}" x2="${X(t)}"/>`;
  s += `</g><g class="axis"><line x1="${m.l}" x2="${m.l}" y1="${m.t}" y2="${H - m.b}"/><line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/></g>`;
  for (const t of o.y.ticks) s += `<text x="${m.l - 6}" y="${Y(t) + 3.5}" text-anchor="end" class="lab">${(o.y.fmt || String)(t)}</text>`;
  for (const t of o.x.ticks) s += `<text x="${X(t)}" y="${H - m.b + 15}" text-anchor="middle" class="lab">${(o.x.fmt || String)(t)}</text>`;
  if (o.x.label) s += `<text x="${(m.l + W - m.r) / 2}" y="${H - 6}" text-anchor="middle" class="lab">${o.x.label}</text>`;
  if (o.y.label) s += `<text transform="translate(12 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle" class="lab">${o.y.label}</text>`;
  for (const se of o.series) {
    const pts = se.x.map((x, i) => [x, se.y[i]]).filter(([x, y]) => x != null && y != null && isFinite(x) && isFinite(y));
    if (!pts.length) continue;
    if (se.segments) {
      for (const seg of se.segments) {
        const sp = seg.map((i) => [se.x[i], se.y[i]]).filter(([x, y]) => y != null && isFinite(y));
        if (sp.length) s += `<polyline fill="none" stroke="${se.color}" stroke-width="${se.width || 1.6}" ${se.dash ? `stroke-dasharray="${se.dash}"` : ""} points="${sp.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ")}"/>`;
      }
    } else if (!se.noLine) {
      s += `<polyline fill="none" stroke="${se.color}" stroke-width="${se.width || 1.8}" stroke-linejoin="round" ${se.dash ? `stroke-dasharray="${se.dash}"` : ""} points="${pts.map(([x, y]) => `${X(x).toFixed(1)},${Y(y).toFixed(1)}`).join(" ")}"/>`;
    }
    if (se.dots) for (const [x, y] of pts) s += `<circle cx="${X(x).toFixed(1)}" cy="${Y(y).toFixed(1)}" r="${se.r || 3}" fill="${se.fill || se.color}" stroke="${se.color}" stroke-width="1"/>`;
  }
  for (const mk of o.marks || []) {
    if (mk.type === "square") s += `<rect x="${X(mk.x) - 5}" y="${Y(mk.y) - 5}" width="10" height="10" fill="${mk.color}"/>`;
    else s += `<circle cx="${X(mk.x)}" cy="${Y(mk.y)}" r="${mk.r || 6}" fill="${mk.color}" stroke="${mk.stroke || "none"}" stroke-width="2"/>`;
    if (mk.text) s += `<text x="${X(mk.x) + 10}" y="${Y(mk.y) + 4}">${mk.text}</text>`;
  }
  if (o.legend) {
    let lx = o.legendX != null ? o.legendX : m.l + 10, ly = o.legendY != null ? o.legendY : (o.y.invert ? H - m.b - 12 - 16 * (o.legend.length - 1) : m.t + 10);
    s += `<g class="legend-row">`;
    for (const lg of o.legend) {
      s += `<line x1="${lx}" x2="${lx + 18}" y1="${ly}" y2="${ly}" stroke="${lg.color}" stroke-width="2" ${lg.dash ? `stroke-dasharray="${lg.dash}"` : ""}/><text x="${lx + 24}" y="${ly + 3.5}">${lg.text}</text>`;
      ly += 16;
    }
    s += `</g>`;
  }
  s += `</svg>`;
  host.innerHTML = s;
}

/* ------------------------------------------------------------------ nav + reveal */
function setupNav() {
  const nav = $("#nav"), darks = $$(".hero, .sec.navy, .foot");
  const upd = () => { const y = 30; nav.classList.toggle("dark", darks.some((d) => { const r = d.getBoundingClientRect(); return r.top <= y && r.bottom >= y; })); };
  addEventListener("scroll", upd, { passive: true }); upd();
  const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12 });
  $$(".sec-head, .sub, .grid-2, .stats, .steps, .table-wrap, .cards4, .impact, .clf, .triptych, .model-card, .map-card, .pinned").forEach((e) => { e.classList.add("reveal"); io.observe(e); });
}

/* ------------------------------------------------------------------ hero: descent */
function setupHero() {
  const hero = $(".hero"), sticky = $(".hero-sticky"), cv = $("#snow"), ctx = cv.getContext("2d");
  const D = META.depths, T = S.profile.mean;
  const tempAt = (d) => { for (let i = 0; i < D.length - 1; i++) if (d <= D[i + 1]) { const f = (d - D[i]) / (D[i + 1] - D[i]); return T[i] + (T[i + 1] - T[i]) * f; } return T[T.length - 1]; };
  const ticks = $("#gaugeTicks"), gaugeH = () => $(".gauge-track").getBoundingClientRect().height;
  const depthToFrac = (d) => Math.sqrt(d / 1000);
  const drawTicks = () => { ticks.innerHTML = [0, 50, 100, 200, 500, 1000].map((d) => `<div style="top:${depthToFrac(d) * gaugeH()}px">${d} m</div>`).join(""); };
  let W, H, parts = [];
  const resize = () => {
    W = cv.width = sticky.clientWidth * DPR; H = cv.height = sticky.clientHeight * DPR; drawTicks();
    parts = Array.from({ length: Math.round((W * H) / (DPR * DPR * 5200)) }, () => ({ x: Math.random() * W, y: Math.random() * H * 3, r: (Math.random() * 1.4 + 0.3) * DPR, s: Math.random() * 0.6 + 0.2, a: Math.random() * 0.5 + 0.15 }));
  };
  resize(); addEventListener("resize", resize);
  let prog = 0;
  const onScroll = () => { const r = hero.getBoundingClientRect(), span = Math.max(1, r.height - sticky.clientHeight); prog = clamp(-r.top / span, 0, 1) || 0; };
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let t0 = performance.now();
  const frame = (now) => {
    onScroll();
    const t = (now - t0) / 1000, depth = 1000 * prog * prog;
    const light = 1 - Math.sqrt(prog);
    sticky.style.background = `linear-gradient(180deg, rgba(${27 + 10 * light},${59 * light + 20},${82 * light + 28},1) 0%, rgba(${18 * light + 11},${41 * light + 20},${58 * light + 28},1) 35%, #0b141c 100%)`;
    ctx.clearRect(0, 0, W, H);
    if (light > 0.02) {   // light rays near the surface
      for (let k = 0; k < 5; k++) {
        const x = W * (0.15 + 0.18 * k) + Math.sin(t * 0.3 + k) * 30 * DPR;
        const g = ctx.createLinearGradient(x, 0, x + 120 * DPR, H * 0.8);
        g.addColorStop(0, `rgba(220,235,240,${0.07 * light})`); g.addColorStop(1, "rgba(220,235,240,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(x - 40 * DPR, 0); ctx.lineTo(x + 40 * DPR, 0); ctx.lineTo(x + 220 * DPR, H); ctx.lineTo(x + 60 * DPR, H); ctx.fill();
      }
    }
    for (const p of parts) {
      const y = ((p.y - prog * H * 2.2 * p.s - (reduce ? 0 : t * 6 * p.s * DPR)) % (H * 3) + H * 3) % (H * 3);
      if (y > H) continue;
      ctx.fillStyle = `rgba(230,235,230,${p.a * (0.5 + 0.5 * (1 - light))})`;
      ctx.beginPath(); ctx.arc(p.x + Math.sin(t * 0.5 + p.y) * 4 * DPR, y, p.r, 0, 6.283); ctx.fill();
    }
    $("#gaugeFill").style.height = `${depthToFrac(depth) * gaugeH()}px`;
    $("#gDepth").textContent = `${Math.round(depth)} m`;
    $("#gTemp").textContent = `${tempAt(depth).toFixed(1)} °C`;
    $(".hero-copy").style.opacity = String(clamp(1 - (prog - 0.55) / 0.35, 0, 1));
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}

/* ------------------------------------------------------------------ stat blocks */
const statHtml = (k, v, unit, l) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}${unit ? `<small>${unit}</small>` : ""}</div><div class="l">${l}</div></div>`;
function setupStats() {
  $("#heroStats").innerHTML =
    statHtml("Dataset", "3.67", "M rows", "one ocean cell on one day, 92 columns, 40 engineered features") +
    statHtml("Grid", "11,880", "cells", "0.25° ocean cells, 365 days, 15 depths from 0 to 1000 m") +
    statHtml("Inputs", "7", "fields", "SST, salinity, sea level, two current and two wind components") +
    statHtml("Floats", "4,071", "profiles", "ARGO profiles in the region in 2021, kept for validation only");
  const F = S.models[S.final], C = S.models.climatology, tol = S.tolerance.overall["1.0"];
  $("#depthStats").innerHTML =
    statHtml("Test RMSE", fmt(F.rmse, 3), "°C", `final model on the four unseen months (climatology ${fmt(C.rmse, 3)} °C)`) +
    statHtml("Improvement", Math.round(100 * (1 - F.rmse / C.rmse)), "%", "lower error than the long-term monthly average") +
    statHtml("Within ±1 °C", fmt(tol.model_pct, 1), "%", `of all test predictions (climatology ${fmt(tol.clim_pct, 1)}%)`) +
    statHtml("Skill", fmt(F.skill, 2), "", "mean over depths; 0 = climatology, 1 = perfect");
  const A = S.argo_stats;
  $("#argoStats").innerHTML =
    statHtml("Matchups", fmtInt(A.n_matchups_cell_days), "", `profiles from ${A.n_floats} floats on test days`) +
    statHtml("ML vs ARGO", fmt(A.overall.pred.rmse, 2), "°C", `RMSE, bias ${fmt(A.overall.pred.bias, 2)} °C`) +
    statHtml("Climatology", fmt(A.overall.clim.rmse, 2), "°C", `RMSE, bias ${fmt(A.overall.clim.bias, 2)} °C (too cold)`) +
    statHtml("GLORYS", fmt(A.overall.glorys.rmse, 2), "°C", "the training target itself: the realistic ceiling");
}

/* ------------------------------------------------------------------ map renderer (shared) */
const NX = 241, NY = 101;
function makeImage(values, range, cmap, landRGB = [26, 40, 51]) {
  const off = document.createElement("canvas"); off.width = NX; off.height = NY;
  const c = off.getContext("2d"), img = c.createImageData(NX, NY), lut = LUT[cmap];
  for (let p = 0; p < NX * NY; p++) { img.data[p * 4] = landRGB[0]; img.data[p * 4 + 1] = landRGB[1]; img.data[p * 4 + 2] = landRGB[2]; img.data[p * 4 + 3] = 255; }
  const { iy, ix } = META.cells;
  for (let i = 0; i < N; i++) {
    const v = values[i], row = NY - 1 - iy[i], p = (row * NX + ix[i]) * 4;
    if (!isFinite(v)) { img.data[p] = 40; img.data[p + 1] = 52; img.data[p + 2] = 62; continue; }
    const k = clamp(Math.round(((v - range[0]) / (range[1] - range[0])) * 255), 0, 255) * 3;
    img.data[p] = lut[k]; img.data[p + 1] = lut[k + 1]; img.data[p + 2] = lut[k + 2];
  }
  c.putImageData(img, 0, 0);
  return off;
}
const lonToX = (lon, w) => ((lon - 44.875) / 60.25) * w;
const latToY = (lat, h) => ((30.125 - lat) / 25.25) * h;
function drawTrack(ctx, w, h, tr, color, width, day) {
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath();
  tr.lat.forEach((la, i) => { const x = lonToX(tr.lon[i], w), y = latToY(la, h); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.stroke();
  if (day) {
    const idx = tr.time.map((t, i) => [Math.abs(new Date(t.replace(" ", "T") + "Z") - new Date(day + "T12:00Z")), i]).sort((a, b) => a[0] - b[0])[0];
    if (idx && idx[0] < 36e5 * 18) {
      const i = idx[1], x = lonToX(tr.lon[i], w), y = latToY(tr.lat[i], h);
      ctx.fillStyle = color; star(ctx, x, y, 7 * DPR);
      return { x, y };
    }
  }
  return null;
}
function star(ctx, x, y, r) { ctx.beginPath(); for (let k = 0; k < 10; k++) { const a = (Math.PI / 5) * k - Math.PI / 2, rr = k % 2 ? r * 0.45 : r; ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } ctx.closePath(); ctx.fill(); }
const activeTracks = (day, pad = 3) => S.tracks.filter((t) => { const a = new Date(t.time[0].slice(0, 10)), b = new Date(t.time[t.time.length - 1].slice(0, 10)), d = new Date(day); return d >= new Date(a - pad * 864e5) && d <= new Date(+b + pad * 864e5); });

/* ------------------------------------------------------------------ explorer */
const EX = { day: "2021-05-14", layer: "temp", src: "pred", depth: 7, pin: null, argo: true, tracks: true };
const LAYERS = { temp: "Temperature", tchp: "Cyclone heat (TCHP)", d20: "Thermocline depth (D20)", inputs: "Satellite inputs" };
const SOURCES = { glorys: "GLORYS (truth)", pred: "ML prediction", clim: "Climatology", err: "Error (ML − truth)" };
const INPUT_NAMES = { sst: ["Sea surface temperature", "°C", 100], sss: ["Sea surface salinity", "PSU", 100], sla: ["Sea level anomaly", "m", 1000], u10: ["Wind speed", "m/s", 100], uo: ["Current speed", "m/s", 1000] };
let exInput = "sla";

function chipGroup(host, items, current, onPick, cls = "") {
  host.innerHTML = "";
  for (const [k, label] of Object.entries(items)) {
    const b = el("button", { class: "chip " + cls + (k === current ? " on" : ""), type: "button", "data-k": k }, label);
    b.addEventListener("click", () => { $$(".chip", host).forEach((x) => x.classList.toggle("on", x === b)); onPick(k); });
    host.appendChild(b);
  }
}

async function exFields() {
  const L = META.layout, arr = await getDay(EX.day), month = +EX.day.slice(5, 7), clim = await getClim(month);
  const out = { glorys: new Float32Array(N), pred: new Float32Array(N), clim: new Float32Array(N) };
  if (EX.layer === "temp") {
    for (let i = 0; i < N; i++) { out.glorys[i] = val(arr, L.glorys + EX.depth, i, 100); out.pred[i] = val(arr, L.pred + EX.depth, i, 100); out.clim[i] = val(clim, EX.depth, i, 100); }
  } else if (EX.layer === "tchp" || EX.layer === "d20") {
    const r0 = L[EX.layer];
    for (let i = 0; i < N; i++) { out.glorys[i] = val(arr, r0, i, 10); out.pred[i] = val(arr, r0 + 1, i, 10); out.clim[i] = val(arr, r0 + 2, i, 10); }
  }
  return { arr, clim, out };
}
function pct(a, p) { const v = Array.from(a).filter(isFinite).sort((x, y) => x - y); return v[Math.floor((v.length - 1) * p)]; }

async function drawExplorer() {
  $("#mapLoading").style.display = "grid";
  let F;
  try { F = await exFields(); } catch (e) { $("#mapLoading").textContent = "Could not load data for this day."; return; }
  $("#mapLoading").style.display = "none";
  const isInput = EX.layer === "inputs";
  $("#depthRow").style.display = EX.layer === "temp" ? "" : "none";
  let values, range, cmap, unit, title;
  if (isInput) {
    const L = META.layout, idx = META.inputs.indexOf(exInput === "u10" ? "u10" : exInput === "uo" ? "uo" : exInput), sc = INPUT_NAMES[exInput][2];
    values = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      if (exInput === "u10") { const u = val(F.arr, L.inputs + 5, i, 100), v = val(F.arr, L.inputs + 6, i, 100); values[i] = Math.hypot(u, v); }
      else if (exInput === "uo") { const u = val(F.arr, L.inputs + 3, i, 1000), v = val(F.arr, L.inputs + 4, i, 1000); values[i] = Math.hypot(u, v); }
      else values[i] = val(F.arr, L.inputs + idx, i, sc);
    }
    range = [pct(values, 0.02), pct(values, 0.98)]; cmap = exInput === "sla" ? "balance" : exInput === "sss" ? "deep" : "thermal"; unit = INPUT_NAMES[exInput][1];
    if (exInput === "sla") { const a = Math.max(Math.abs(range[0]), Math.abs(range[1])); range = [-a, a]; }
    if (exInput === "sss") range = [range[1], range[0]];
    title = INPUT_NAMES[exInput][0];
  } else {
    const o = F.out;
    if (EX.src === "err") {
      values = new Float32Array(N); for (let i = 0; i < N; i++) values[i] = o.pred[i] - o.glorys[i];
      const a = EX.layer === "temp" ? clamp(Math.ceil(pct(values.map(Math.abs), 0.98) * 2) / 2, 0.5, 4) : 40;
      range = [-a, a]; cmap = "balance";
    } else {
      values = o[EX.src];
      if (EX.layer === "temp") { range = [pct(o.glorys, 0.01), pct(o.glorys, 0.99)]; cmap = "thermal"; }
      else if (EX.layer === "tchp") { range = [0, 150]; cmap = "heat"; }
      else { range = [200, 40]; cmap = "deep"; }
    }
    unit = EX.layer === "temp" ? "°C" : EX.layer === "tchp" ? "kJ/cm²" : "m";
    title = `${LAYERS[EX.layer]}${EX.layer === "temp" ? ` · ${META.depths[EX.depth]} m` : ""} · ${SOURCES[EX.src]}`;
  }
  EX.values = values; EX.unit = unit; EX.F = F;
  $("#mapTitle").textContent = title;
  const rmse = (() => { if (isInput) return null; const o = F.out; let s = 0, n = 0, sc = 0; for (let i = 0; i < N; i++) { const e = o.pred[i] - o.glorys[i], ec = o.clim[i] - o.glorys[i]; if (isFinite(e) && isFinite(ec)) { s += e * e; sc += ec * ec; n++; } } return [Math.sqrt(s / n), Math.sqrt(sc / n)]; })();
  $("#mapSub").textContent = `${dayLabel(EX.day)} · unseen test day` + (rmse ? ` · domain RMSE  ML ${fmt(rmse[0], 2)} ${unit}  ·  climatology ${fmt(rmse[1], 2)} ${unit}` : "");
  const lo = range[0], hi = range[1], ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => lo + (hi - lo) * f);
  $("#legend").innerHTML = `<div class="bar" style="background:${cmapCss(cmap)}"></div><div class="ticks">${ticks.map((t) => `<span>${fmt(t, Math.abs(hi - lo) < 3 ? 2 : Math.abs(hi - lo) < 30 ? 1 : 0)}</span>`).join("")}</div><div class="ticks"><span>${unit}</span></div>`;
  EX.img = makeImage(values, range, cmap);
  paintMap();
  drawPin();
}

function paintMap() {
  const cv = $("#map"), box = $("#mapBox"), w = box.clientWidth - 36, h = Math.round((w * NY) / NX);
  cv.style.height = h + "px"; cv.width = w * DPR; cv.height = h * DPR;
  const ctx = cv.getContext("2d"); ctx.imageSmoothingEnabled = false;
  ctx.drawImage(EX.img, 0, 0, cv.width, cv.height);
  const W = cv.width, H = cv.height;
  ctx.strokeStyle = "rgba(239,232,220,.10)"; ctx.lineWidth = 1; ctx.fillStyle = "rgba(239,232,220,.45)"; ctx.font = `${10 * DPR}px "IBM Plex Mono", monospace`;
  for (let lon = 50; lon <= 100; lon += 10) { const x = lonToX(lon, W); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); ctx.fillText(`${lon}°E`, x + 3 * DPR, H - 5 * DPR); }
  for (let lat = 10; lat <= 25; lat += 5) { const y = latToY(lat, H); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); ctx.fillText(`${lat}°N`, 4 * DPR, y - 4 * DPR); }
  ctx.fillStyle = "rgba(239,232,220,.55)"; ctx.font = `${11 * DPR}px "IBM Plex Mono", monospace`;
  [["INDIA", 78, 21], ["ARABIAN SEA", 63, 14.5], ["BAY OF BENGAL", 88.6, 15.2], ["SRI LANKA", 80.8, 6.2]].forEach(([t, lo, la]) => { ctx.textAlign = "center"; ctx.fillText(t, lonToX(lo, W), latToY(la, H)); });
  ctx.textAlign = "left";
  if (EX.tracks) {
    const act = activeTracks(EX.day, 1);
    for (const tr of S.tracks) if (!act.includes(tr)) drawTrack(ctx, W, H, tr, "rgba(239,232,220,.16)", 1 * DPR);
    for (const tr of act) { const p = drawTrack(ctx, W, H, tr, "rgba(239,232,220,.95)", 2 * DPR, EX.day); if (p) { ctx.fillStyle = "#efe8dc"; ctx.font = `${11 * DPR}px "IBM Plex Mono", monospace`; ctx.fillText(tr.name, p.x + 10 * DPR, p.y - 8 * DPR); } }
  }
  if (EX.argo) {
    const A = S.argo; ctx.strokeStyle = "#7fe0b4"; ctx.lineWidth = 2 * DPR;
    A.time.forEach((t, k) => { if (t !== EX.day) return; const x = ((A.ix[k] + 0.5) / NX) * W, y = ((NY - 0.5 - A.iy[k]) / NY) * H; ctx.beginPath(); ctx.arc(x, y, 4.5 * DPR, 0, 6.283); ctx.stroke(); });
  }
  if (EX.pin != null) {
    const i = EX.pin, x = ((META.cells.ix[i] + 0.5) / NX) * W, y = ((NY - 0.5 - META.cells.iy[i]) / NY) * H, c = (W / NX) * 1.6;
    ctx.strokeStyle = "#f3d14b"; ctx.lineWidth = 2 * DPR; ctx.strokeRect(x - c / 2, y - c / 2, c, c);
    ctx.beginPath(); ctx.moveTo(x - c * 2, y); ctx.lineTo(x - c, y); ctx.moveTo(x + c, y); ctx.lineTo(x + c * 2, y); ctx.moveTo(x, y - c * 2); ctx.lineTo(x, y - c); ctx.moveTo(x, y + c); ctx.lineTo(x, y + c * 2); ctx.stroke();
  }
}

function cellAt(ev) {
  const cv = $("#map"), r = cv.getBoundingClientRect(), ix = Math.floor(((ev.clientX - r.left) / r.width) * NX), row = Math.floor(((ev.clientY - r.top) / r.height) * NY), iy = NY - 1 - row;
  if (ix < 0 || ix >= NX || iy < 0 || iy >= NY) return -1;
  return CELLIDX[iy * NX + ix];
}
function argoAt(i, day) { const A = S.argo; for (let k = 0; k < A.time.length; k++) if (A.time[k] === day && A.ix[k] === META.cells.ix[i] && A.iy[k] === META.cells.iy[i]) return k; return -1; }

function drawPin() {
  const i = EX.pin; if (i == null || !EX.F) return;
  const L = META.layout, arr = EX.F.arr, clim = EX.F.clim;
  const lat = META.lat[META.cells.iy[i]], lon = META.lon[META.cells.ix[i]];
  $("#pinCoord").textContent = `${lat.toFixed(2)}°N  ${lon.toFixed(2)}°E`;
  $("#pinDay").textContent = dayLabel(EX.day).toUpperCase();
  const g = (row, sc) => val(arr, row, i, sc);
  const sst = g(L.inputs, 100), sss = g(L.inputs + 1, 100), sla = g(L.inputs + 2, 1000), cur = Math.hypot(g(L.inputs + 3, 1000), g(L.inputs + 4, 1000)), wind = Math.hypot(g(L.inputs + 5, 100), g(L.inputs + 6, 100));
  const tchpT = g(L.tchp, 10), tchpP = g(L.tchp + 1, 10), d20T = g(L.d20, 10), d20P = g(L.d20 + 1, 10);
  const yT = META.depths.map((_, k) => g(L.glorys + k, 100)), yP = META.depths.map((_, k) => g(L.pred + k, 100)), yC = META.depths.map((_, k) => val(clim, k, i, 100));
  let se = 0, sc = 0, n = 0; yT.forEach((t, k) => { if (isFinite(t) && isFinite(yP[k])) { se += (yP[k] - t) ** 2; sc += (yC[k] - t) ** 2; n++; } });
  const ro = (v, l, cls = "") => `<div class="ro ${cls}"><div class="v ${cls.includes("fog") ? "fog" : ""}">${v}</div><div class="l">${l}</div></div>`;
  $("#readouts").innerHTML =
    ro(fmt(sst, 2), "SST °C · input") + ro(fmt(sss, 2), "SSS PSU · input") + ro(fmt(sla, 3), "SEA LEVEL ANOMALY m · input") +
    ro(`${fmt(wind, 1)} <small style="font-size:14px;opacity:.6">/ ${fmt(cur, 2)}</small>`, "WIND m/s / CURRENT m/s · inputs") +
    ro(`${fmt(tchpP, 0)} <small style="font-size:14px;opacity:.6">vs ${fmt(tchpT, 0)}</small>`, "TCHP kJ/cm² · ML vs truth", "fog") +
    ro(`${fmt(d20P, 0)} <small style="font-size:14px;opacity:.6">vs ${fmt(d20T, 0)}</small>`, "D20 m · ML vs truth", "fog") +
    ro(`${fmt(Math.sqrt(se / n), 2)} <small style="font-size:14px;opacity:.6">vs ${fmt(Math.sqrt(sc / n), 2)}</small>`, `COLUMN RMSE °C · ML vs CLIMATOLOGY (${n} DEPTHS)`, "wide fog");
  const D = META.depths, series = [
    { x: yC, y: D, color: "rgba(239,232,220,.45)", dash: "4 4", width: 1.4 },
    { x: yT, y: D, color: "#efe8dc", width: 2, dots: true, r: 2.5, fill: "#0b141c" },
    { x: yP, y: D, color: "#c9a86a", width: 2.2, dots: true, r: 2.5 },
  ];
  const legend = [{ text: "GLORYS (truth)", color: "#efe8dc" }, { text: "ML prediction", color: "#c9a86a" }, { text: "Climatology", color: "rgba(239,232,220,.45)", dash: "4 4" }];
  const ak = argoAt(i, EX.day);
  if (ak >= 0) { series.push({ x: S.argo.argo[ak], y: D, color: "#7fe0b4", noLine: false, width: 1.2, dots: true, r: 3, dash: "2 3" }); legend.push({ text: `ARGO float ${S.argo.platform[ak]}`, color: "#7fe0b4", dash: "2 3" }); }
  const all = [...yT, ...yP, ...yC].filter(isFinite), lo = Math.floor(Math.min(...all) - 0.5), hi = Math.ceil(Math.max(...all) + 0.5);
  const xt = []; for (let t = Math.ceil(lo / 5) * 5; t <= hi; t += 5) xt.push(t);
  $("#profSub").textContent = ak >= 0 ? "an ARGO float profiled this cell on this day" : "click a green ARGO circle to compare with a real float";
  chart($("#profChart"), { w: 520, h: 360, x: { min: lo, max: hi, ticks: xt, label: "temperature °C" }, y: { min: 0, max: 1000, invert: true, sqrt: true, ticks: DEPTH_TICKS, label: "depth m" }, series, legend, legendX: 300, label: "temperature profile",
    bands: [{ y: [50, 200], fill: "rgba(201,168,106,.07)", text: "thermocline" }] });
}

function setupExplorer() {
  const sel = $("#daySel");
  META.days.forEach((d) => { const o = el("option", { value: d }, dayLabel(d) + (d === "2021-05-14" ? " · Tauktae" : d === "2021-05-24" ? " · Yaas" : "")); sel.appendChild(o); });
  sel.value = EX.day; sel.addEventListener("change", () => { EX.day = sel.value; drawExplorer(); });
  chipGroup($("#layerChips"), LAYERS, EX.layer, (k) => { EX.layer = k; if (k === "inputs") { renderInputChips(); } else { chipGroup($("#srcChips"), SOURCES, EX.src, (s) => { EX.src = s; drawExplorer(); }); } drawExplorer(); });
  const renderInputChips = () => chipGroup($("#srcChips"), { sla: "Sea level", sst: "SST", sss: "Salinity", u10: "Wind speed", uo: "Current speed" }, exInput, (k) => { exInput = k; drawExplorer(); });
  chipGroup($("#srcChips"), SOURCES, EX.src, (k) => { EX.src = k; drawExplorer(); });
  chipGroup($("#depthChips"), Object.fromEntries(META.depths.map((d, k) => [k, `${d} m`])), String(EX.depth), (k) => { EX.depth = +k; drawExplorer(); });
  $("#argoTog").addEventListener("change", (e) => { EX.argo = e.target.checked; paintMap(); });
  $("#trackTog").addEventListener("change", (e) => { EX.tracks = e.target.checked; paintMap(); });
  const cv = $("#map"), tip = $("#tip");
  cv.addEventListener("mousemove", (ev) => {
    const i = cellAt(ev); if (i < 0 || !EX.values) { tip.style.display = "none"; return; }
    const lat = META.lat[META.cells.iy[i]], lon = META.lon[META.cells.ix[i]], v = EX.values[i];
    let extra = "";
    if (EX.layer !== "inputs") { const o = EX.F.out; extra = `<br>truth ${fmt(o.glorys[i], 2)} · ML ${fmt(o.pred[i], 2)} · clim ${fmt(o.clim[i], 2)}`; }
    tip.innerHTML = `${lat.toFixed(2)}°N ${lon.toFixed(2)}°E<br><b>${fmt(v, 2)} ${EX.unit}</b>${extra}`;
    const r = $("#mapBox").getBoundingClientRect(); let x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
    if (x > r.width - 230) x -= 250;
    tip.style.left = x + "px"; tip.style.top = y + "px"; tip.style.display = "block";
  });
  cv.addEventListener("mouseleave", () => (tip.style.display = "none"));
  cv.addEventListener("click", (ev) => { const i = cellAt(ev); if (i >= 0) { EX.pin = i; paintMap(); drawPin(); } });
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => EX.img && paintMap(), 120); });
  // default pin: an ARGO cell on the default day if one exists, else 15N 65E
  const A = S.argo; let k = -1, best = 0;
  A.time.forEach((t, j) => { if (t !== EX.day) return; const n = A.argo[j].filter((v) => v != null).length; if (n > best) { best = n; k = j; } });
  EX.pin = k >= 0 ? CELLIDX[A.iy[k] * NX + A.ix[k]] : CELLIDX[40 * NX + 80];
  drawExplorer();
}

/* ------------------------------------------------------------------ depth section */
function setupDepth() {
  const D = META.depths, M = S.models, F = M[S.final];
  const xs = (m) => M[m].per_depth;
  chart($("#depthChart"), {
    w: 520, h: 380, x: { min: 0, max: 1.9, ticks: [0, 0.5, 1, 1.5], label: "RMSE °C" }, y: { min: 0, max: 1000, invert: true, sqrt: true, ticks: DEPTH_TICKS, label: "depth m" },
    bands: [{ y: [50, 200], fill: "rgba(201,168,106,.13)", text: "thermocline" }],
    series: [
      { x: xs("climatology"), y: D, color: "#8a8f96", dash: "5 4", width: 1.6, dots: true, r: 2.4, fill: "#f1ebe1" },
      { x: xs("linear_regression"), y: D, color: "#2f5d8a", width: 1.3 },
      { x: xs("gradient_boosting"), y: D, color: "#2f6b63", width: 1.3 },
      { x: F.per_depth, y: D, color: "#b4532a", width: 2.6, dots: true, r: 3 },
    ],
    legend: [{ text: "Final model", color: "#b4532a" }, { text: "Gradient boosting (no clim. feature)", color: "#2f6b63" }, { text: "Linear regression", color: "#2f5d8a" }, { text: "Climatology baseline", color: "#8a8f96", dash: "5 4" }], legendX: 250,
    label: "RMSE by depth",
  });
  const T = S.tolerance.per_depth_within_1C;
  chart($("#tolChart"), {
    w: 520, h: 380, x: { min: 30, max: 100, ticks: [40, 60, 80, 100], label: "% within ±1 °C", fmt: (t) => t + "%" }, y: { min: 0, max: 1000, invert: true, sqrt: true, ticks: DEPTH_TICKS, label: "depth m" },
    bands: [{ y: [50, 200], fill: "rgba(201,168,106,.13)" }],
    series: [
      { x: D.map((d) => T[String(d)]?.clim_pct), y: D, color: "#8a8f96", dash: "5 4", width: 1.6, dots: true, r: 2.4, fill: "#f1ebe1" },
      { x: D.map((d) => T[String(d)]?.model_pct), y: D, color: "#b4532a", width: 2.6, dots: true, r: 3 },
    ],
    legend: [{ text: "Final model", color: "#b4532a" }, { text: "Climatology", color: "#8a8f96", dash: "5 4" }], legendY: 300,
    label: "share within one degree",
  });
  const B = S.breakdown, R = { arabian_sea: "Arabian Sea", bay_of_bengal: "Bay of Bengal", other: "Gulfs, Andaman and south" };
  let h = "";
  for (const [k, n] of Object.entries(R)) {
    const b = B.region[k];
    h += `<div class="bcard"><div class="k">Region · ${fmtInt(b.n)} rows</div><div class="t">${n}</div>
      <div class="row">Final model <b>${fmt(b.rmse, 3)} °C</b></div><div class="row">Climatology <b>${fmt(b.clim, 3)} °C</b></div><div class="row">At 100 m <b>${fmt(b.rmse100, 2)} °C</b></div>
      <div class="bar-mini"><span style="width:${100 * (1 - b.rmse / b.clim)}%"></span></div><div class="row" style="font-size:11px">error reduction <b>${Math.round(100 * (1 - b.rmse / b.clim))}%</b></div></div>`;
  }
  const mn = { 2: "February", 5: "May", 8: "August", 11: "November" };
  h += `<div class="bcard"><div class="k">Season · test month</div><div class="t">All four seasons</div>${Object.entries(mn).map(([m, n]) => `<div class="row">${n} <b>${fmt(B.month[m].rmse, 3)} °C</b></div>`).join("")}</div>`;
  $("#breakCards").innerHTML = h;
}

/* ------------------------------------------------------------------ ARGO */
let argoRegion = "all";
function drawArgoScatter() {
  const host = $("#argoScatter"), A = S.argo, W = 520, H = 400, m = { l: 48, r: 14, t: 14, b: 40 }, lo = 4, hi = 33;
  host.innerHTML = `<canvas style="width:100%;display:block"></canvas>`;
  const cv = host.firstChild, w = host.clientWidth || W, h = (w * H) / W;
  cv.width = w * DPR; cv.height = h * DPR; cv.style.height = h + "px";
  const ctx = cv.getContext("2d"), s = (w * DPR) / W; ctx.scale(s, s);
  const X = scaleLin(lo, hi, m.l, W - m.r), Y = scaleLin(lo, hi, H - m.b, m.t), lut = LUT.thermal;
  ctx.strokeStyle = "rgba(22,25,31,.08)"; ctx.fillStyle = "rgba(22,25,31,.6)"; ctx.font = '10.5px "IBM Plex Mono", monospace'; ctx.textAlign = "center";
  for (let t = 5; t <= 30; t += 5) { ctx.beginPath(); ctx.moveTo(X(t), m.t); ctx.lineTo(X(t), H - m.b); ctx.moveTo(m.l, Y(t)); ctx.lineTo(W - m.r, Y(t)); ctx.stroke(); ctx.fillText(t, X(t), H - m.b + 15); ctx.textAlign = "right"; ctx.fillText(t, m.l - 6, Y(t) + 3.5); ctx.textAlign = "center"; }
  ctx.fillText("ARGO potential temperature °C", (m.l + W - m.r) / 2, H - 6);
  ctx.save(); ctx.translate(12, (m.t + H - m.b) / 2); ctx.rotate(-Math.PI / 2); ctx.fillText("ML prediction °C", 0, 0); ctx.restore();
  ctx.strokeStyle = "rgba(22,25,31,.5)"; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(X(lo), Y(lo)); ctx.lineTo(X(hi), Y(hi)); ctx.stroke(); ctx.setLineDash([]);
  let n = 0, se = 0;
  for (let k = A.time.length - 1; k >= 0; k--) {
    if (argoRegion !== "all" && A.region[k] !== argoRegion) continue;
    for (let d = 0; d < 15; d++) {
      const a = A.argo[k][d], p = A.pred[k][d]; if (a == null || p == null) continue;
      const c = Math.round((1 - Math.sqrt(META.depths[d] / 1000)) * 230) * 3;
      ctx.fillStyle = `rgba(${lut[c]},${lut[c + 1]},${lut[c + 2]},.55)`; ctx.fillRect(X(a) - 1.4, Y(p) - 1.4, 2.8, 2.8);
      n++; se += (p - a) ** 2;
    }
  }
  $("#argoScatSub").textContent = `${fmtInt(n)} depth-points · RMSE ${fmt(Math.sqrt(se / n), 2)} °C · colour = depth (bright = surface, dark = 1000 m)`;
}
function setupArgo() {
  const head = $("#argo .wrap .stats");
  const chips = el("div", { class: "chips light", style: "margin-top:24px" }); head.after(chips);
  chipGroup(chips, { all: "All regions", arabian_sea: "Arabian Sea", bay_of_bengal: "Bay of Bengal" }, "all", (k) => { argoRegion = k; drawArgoScatter(); });
  drawArgoScatter(); let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawArgoScatter, 150); });
  const P = S.argo_stats.per_depth, D = META.depths.filter((d) => P[String(d)]);
  const g = (w) => D.map((d) => P[String(d)][w].rmse);
  chart($("#argoDepth"), {
    w: 520, h: 400, x: { min: 0, max: 1.8, ticks: [0, 0.4, 0.8, 1.2, 1.6], label: "RMSE against ARGO °C" }, y: { min: 0, max: 1000, invert: true, sqrt: true, ticks: DEPTH_TICKS, label: "depth m" },
    bands: [{ y: [50, 200], fill: "rgba(201,168,106,.13)", text: "thermocline" }],
    series: [{ x: g("clim"), y: D, color: "#8a8f96", dash: "5 4", dots: true, r: 2.4, fill: "#f7f3ec" }, { x: g("glorys"), y: D, color: "#2f5d8a", dots: true, r: 2.4 }, { x: g("pred"), y: D, color: "#b4532a", width: 2.6, dots: true, r: 3 }],
    legend: [{ text: "ML prediction", color: "#b4532a" }, { text: "GLORYS (ceiling)", color: "#2f5d8a" }, { text: "Climatology", color: "#8a8f96", dash: "5 4" }], legendX: 300,
    label: "RMSE against ARGO by depth",
  });
}

/* ------------------------------------------------------------------ cyclones */
const CYC = { Tauktae: "2021-05-14", Yaas: "2021-05-24" };
async function drawCyclone(name) {
  const day = CYC[name], arr = await getDay(day), L = META.layout, tr = S.tracks.find((t) => t.name === name);
  const f = (row) => { const v = new Float32Array(N); for (let i = 0; i < N; i++) v[i] = val(arr, row, i, 10); return v; };
  const T = f(L.tchp), P = f(L.tchp + 1), C = f(L.tchp + 2);
  const rm = (a) => { let s = 0, n = 0; for (let i = 0; i < N; i++) if (isFinite(a[i]) && isFinite(T[i])) { s += (a[i] - T[i]) ** 2; n++; } return Math.sqrt(s / n); };
  const wmax = Math.max(...tr.wind.filter((x) => x != null));
  const near = tr.time.map((t, i) => [Math.abs(new Date(t.replace(" ", "T") + "Z") - new Date(day + "T12:00Z")), i]).sort((a, b) => a[0] - b[0])[0][1];
  $("#cycHead").innerHTML = `<div><div class="k">Storm · date shown</div><div class="v">${name} · ${dayLabel(day)}</div></div>
    <div><div class="k">Peak wind / on this day</div><div class="v">${wmax} kt / ${tr.wind[near] ?? "–"} kt</div></div>
    <div><div class="k">TCHP RMSE · ML</div><div class="v">${fmt(rm(P), 1)} kJ/cm²</div></div>
    <div><div class="k">TCHP RMSE · climatology</div><div class="v">${fmt(rm(C), 1)} kJ/cm²</div></div>`;
  const host = $("#triptych"); host.innerHTML = "";
  [["GLORYS (truth)", T], ["ML prediction", P], ["Climatology", C]].forEach(([t, v]) => {
    const card = el("div", { class: "trip" }, `<div class="tt"><span>${t}</span><span>TCHP kJ/cm²</span></div><canvas></canvas>`); host.appendChild(card);
    const cv = $("canvas", card), w = card.clientWidth - 20, h = Math.round((w * NY) / NX);
    cv.width = w * DPR; cv.height = h * DPR; cv.style.height = h + "px";
    const ctx = cv.getContext("2d"); ctx.imageSmoothingEnabled = false; ctx.drawImage(makeImage(v, [0, 150], "heat", [26, 40, 51]), 0, 0, cv.width, cv.height);
    const p = drawTrack(ctx, cv.width, cv.height, tr, "#0b141c", 2 * DPR, day);
    if (p) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5 * DPR; ctx.beginPath(); ctx.arc(p.x, p.y, 10 * DPR, 0, 6.283); ctx.stroke(); }
  });
  host.appendChild(el("div", { class: "vlegend" }, `<div class="vbar" style="background:${cmapCssV("heat")}"></div><div class="vt"><span>150</span><span>100</span><span>60</span><span>0</span></div>`));
}
let dailyDepth = "100";
function drawDaily() {
  const d = S.daily, dates = d.dates.map((s) => new Date(s + "T00:00Z").getTime() / 864e5), segs = [];
  let cur = [];
  dates.forEach((t, i) => { if (i && t - dates[i - 1] > 1) { segs.push(cur); cur = []; } cur.push(i); }); segs.push(cur);
  const x0 = dates[0], x1 = dates[dates.length - 1], mx = Math.max(...d[`clim_${dailyDepth}`].filter((v) => v != null));
  const cyc = ["Tauktae", "Yaas"].map((n) => { const t = S.tracks.find((q) => q.name === n); return { x: [new Date(t.time[0].slice(0, 10) + "T00:00Z") / 864e5, new Date(t.time[t.time.length - 1].slice(0, 10) + "T00:00Z") / 864e5 + 1], fill: "rgba(22,25,31,.08)", text: n }; });
  const ticks = [2, 5, 8, 11].map((m) => new Date(Date.UTC(2021, m - 1, 1)) / 864e5);
  chart($("#dailyChart"), {
    w: 520, h: 300, x: { min: x0, max: x1, ticks, fmt: (t) => MONTHS[new Date(t * 864e5).getUTCMonth()] }, y: { min: 0, max: Math.ceil(mx * 4) / 4, ticks: [0, 0.5, 1, 1.5, 2].filter((v) => v <= mx + 0.25), label: "RMSE °C" },
    bands: cyc,
    series: [{ x: dates, y: d[`clim_${dailyDepth}`], color: "#8a8f96", dash: "4 3", segments: segs, width: 1.5 }, { x: dates, y: d[`pred_${dailyDepth}`], color: "#b4532a", segments: segs, width: 2 }],
    legend: [{ text: "ML prediction", color: "#b4532a" }, { text: "Climatology", color: "#8a8f96", dash: "4 3" }], legendY: 22,
    label: "daily RMSE",
  });
}
function setupCyclones() {
  chipGroup($("#cycChips"), { Tauktae: "Tauktae · Arabian Sea · 14 May", Yaas: "Yaas · Bay of Bengal · 24 May" }, "Tauktae", drawCyclone);
  drawCyclone("Tauktae");
  chipGroup($("#dailyChips"), { 0: "0 m", 100: "100 m", 300: "300 m" }, "100", (k) => { dailyDepth = k; drawDaily(); }, "light");
  $("#dailyChips").classList.add("light"); drawDaily();
  const I = S.indicators, names = { D20: ["D20", "m", "depth of 20 °C (thermocline)"], D26: ["D26", "m", "depth of 26 °C (warm layer)"], TCHP: ["TCHP", "kJ/cm²", "cyclone heat potential"], MLD: ["MLD", "m", "mixed layer depth"], OHC300: ["OHC300", "GJ/m²", "heat in top 300 m"] };
  $("#indTable").innerHTML = `<table class="ind"><thead><tr><th>Indicator</th><th class="num">ML</th><th class="num">Clim.</th><th>Error removed</th><th class="num">r</th></tr></thead><tbody>${Object.entries(names).map(([k, [n, u, d]]) => {
    const a = I[k].model_vs_glorys, c = I[k].clim_vs_glorys, red = 1 - a.rmse / c.rmse;
    return `<tr><td><b>${n}</b> <span style="color:var(--ink-3);font-size:12px">${d}</span></td><td class="num mono">${fmt(a.rmse, k === "OHC300" ? 2 : 1)} ${u}</td><td class="num mono">${fmt(c.rmse, k === "OHC300" ? 2 : 1)}</td><td><span class="imp" style="width:${Math.round(red * 90)}px"></span><span class="mono">${Math.round(red * 100)}%</span></td><td class="num mono">${fmt(a.r, 2)}</td></tr>`;
  }).join("")}</tbody></table>`;
}

/* ------------------------------------------------------------------ models */
const MODEL_INFO = {
  final_gb_clim_feature: ["Final model", "Boosting · selected", "Gradient boosting with the climatology at each depth as an extra input. The model learns how far to trust the long-term average at every place and depth, which matters because 2021 departed from it (the Bay of Bengal ran warm all year)."],
  ensemble_avg: ["Averaging ensemble", "Ensemble · not adopted", "Average of gradient boosting and random forest. It improved cross-validation by only 0.004% while training five times slower, below our 1% adoption rule set before testing."],
  gradient_boosting: ["Gradient boosting", "Boosting", "Shallow trees added one after another, each fitting the errors left by the previous ones, with a small learning rate (shrinkage). Handles missing values and non-linear, region-dependent effects."],
  random_forest: ["Random forest", "Bagging", "Many deep trees on bootstrap samples, each split choosing from a random subset of features; averaging decorrelated trees reduces variance."],
  bagging_trees: ["Bagging", "Bagging", "Deep trees trained on bootstrap samples and averaged. Same idea as a random forest without random feature subsets."],
  pca_regression: ["PCA regression", "Dimensionality reduction", "Compresses the 15-depth anomaly profile into 8 principal components (vertical modes), predicts those, and rebuilds the profile."],
  svr_rbf: ["Support vector regression", "Kernel method", "Fits a smooth function in an RBF kernel space, ignoring errors inside a margin. Strong, but training cost grows quickly, so it saw only 10,000 rows."],
  knn: ["K-nearest neighbours", "Instance based", "Averages the 40 most similar training rows in standardised feature space. Simple but hurt by many weakly useful features."],
  ridge: ["Ridge regression", "Linear · L2", "Linear regression with a penalty on squared weights. With 400,000 rows and 40 features the penalty barely matters."],
  linear_regression: ["Linear regression", "Linear", "Least-squares weighted sum of the 40 features, one model per depth."],
  lasso: ["Lasso regression", "Linear · L1", "Linear regression with an absolute-value penalty that can switch features off entirely, giving feature selection."],
  linear_gd_scratch: ["Gradient descent (own code)", "Linear · from scratch", "Linear regression trained with our own mini-batch gradient descent in NumPy; it converges to almost the same answer as the library solver."],
  decision_tree: ["Decision tree", "Tree", "A single tree of yes/no questions (depth 8). Interpretable but coarse and unstable."],
  sst_only_linear: ["SST-only regression", "Baseline", "Predicts every depth from sea surface temperature alone. Shows that the surface temperature by itself is not enough."],
  climatology: ["Climatology", "Baseline", "The multi-decade average for each place, month and depth: the forecast you make with no satellite data at all."],
};
let modelSel = null, modelSort = ["rmse", 1];
function drawModel(k) {
  modelSel = k; const m = S.models[k], [name, fam, desc] = MODEL_INFO[k] || [k, "", ""], D = META.depths;
  const prm = m.params && Object.keys(m.params).length ? Object.entries(m.params).map(([a, b]) => `${a} = ${b}`).join(", ") : "none";
  const order = Object.keys(S.models).sort((a, b) => S.models[a].rmse - S.models[b].rmse), mx = Math.max(...order.map((o) => S.models[o].rmse));
  $("#modelCard").innerHTML = `<div><div class="tag">${fam}</div><h3>${name}</h3><p>${desc}</p><p class="mono" style="font-size:12px;color:var(--fog-3)">tuned: ${prm}</p>
    <div class="kv"><div><b>${fmt(m.rmse, 3)}</b><span>TEST RMSE °C</span></div><div><b>${fmt(m.skill, 2)}</b><span>SKILL</span></div><div><b>${m.cv != null ? fmt(m.cv, 3) : "–"}</b><span>CV RMSE °C</span></div><div><b>${m.fit_s != null ? Math.round(m.fit_s) + " s" : "–"}</b><span>TRAIN TIME</span></div></div></div>
    <div><div class="mono" style="font-size:11px;color:var(--fog-3);margin-bottom:6px">RMSE BY DEPTH · selected vs final vs climatology</div><div id="mDepth" class="chart"></div></div>`;
  chart($("#mDepth"), { w: 460, h: 300, x: { min: 0, max: 1.9, ticks: [0, 0.5, 1, 1.5], label: "RMSE °C" }, y: { min: 0, max: 1000, invert: true, sqrt: true, ticks: DEPTH_TICKS },
    bands: [{ y: [50, 200], fill: "rgba(201,168,106,.06)" }],
    series: [{ x: S.models.climatology.per_depth, y: D, color: "rgba(239,232,220,.4)", dash: "4 4" }, ...(k === S.final ? [] : [{ x: S.models[S.final].per_depth, y: D, color: "rgba(239,232,220,.85)", width: 1.4 }]), { x: m.per_depth, y: D, color: "#c9a86a", width: 2.6, dots: true, r: 2.6 }],
    legend: [{ text: name, color: "#c9a86a" }, ...(k === S.final ? [] : [{ text: "Final model", color: "rgba(239,232,220,.85)" }]), ...(k === "climatology" ? [] : [{ text: "Climatology", color: "rgba(239,232,220,.4)", dash: "4 4" }])], legendX: 230 });
  $$(".chip", $("#modelChips")).forEach((c) => c.classList.toggle("on", c.dataset.k === k));
  $$("#modelTable tbody tr").forEach((r) => r.classList.toggle("sel", r.dataset.k === k));
}
function drawModelTable() {
  const keys = Object.keys(S.models), [col, dir] = modelSort;
  const get = (k) => (col === "name" ? (MODEL_INFO[k] || [k])[0] : S.models[k][col] ?? Infinity);
  keys.sort((a, b) => (get(a) > get(b) ? 1 : get(a) < get(b) ? -1 : 0) * dir);
  const mx = Math.max(...keys.map((k) => S.models[k].rmse));
  const th = (c, t, num) => `<th class="sortable ${num ? "num" : ""}" data-c="${c}">${t}${col === c ? (dir > 0 ? " ↑" : " ↓") : ""}</th>`;
  $("#modelTable").innerHTML = `<thead><tr>${th("name", "Model")}<th>Family</th>${th("cv", "CV RMSE", 1)}${th("rmse", "Test RMSE", 1)}<th></th>${th("skill", "Skill", 1)}${th("fit_s", "Train", 1)}</tr></thead><tbody>${keys.map((k) => {
    const m = S.models[k], [n, f] = MODEL_INFO[k] || [k, ""];
    return `<tr data-k="${k}"><td>${n}</td><td style="font-size:12.5px">${f}</td><td class="num">${m.cv != null ? fmt(m.cv, 3) : "–"}</td><td class="num">${fmt(m.rmse, 3)}</td><td style="width:22%"><div class="bars"><div class="row${k === modelSel ? " me" : ""}" style="grid-template-columns:1fr;margin:0"><div class="track"><div class="fill" style="width:${(100 * m.rmse) / mx}%;${k === S.final ? "background:var(--gold)" : ""}"></div></div></div></div></td><td class="num">${fmt(m.skill, 2)}</td><td class="num">${m.fit_s != null ? Math.round(m.fit_s) + " s" : "–"}</td></tr>`;
  }).join("")}</tbody>`;
  $$("#modelTable th.sortable").forEach((t) => t.addEventListener("click", () => { modelSort = [t.dataset.c, modelSort[0] === t.dataset.c ? -modelSort[1] : 1]; drawModelTable(); drawModel(modelSel); }));
  $$("#modelTable tbody tr").forEach((r) => r.addEventListener("click", () => drawModel(r.dataset.k)));
}
function setupModels() {
  const order = Object.keys(S.models).sort((a, b) => S.models[a].rmse - S.models[b].rmse);
  chipGroup($("#modelChips"), Object.fromEntries(order.map((k) => [k, (MODEL_INFO[k] || [k])[0]])), S.final, drawModel);
  drawModelTable(); drawModel(S.final);
}

/* ------------------------------------------------------------------ classifier */
let clfModel = "logistic_l1";
function drawClf() {
  const sw = S.clf_sweep[clfModel], t = +$("#thr").value, i = t - 1, [tp, fp, fn, tn] = sw.tp_fp_fn_tn[i], n = tp + fp + fn + tn;
  $("#thrVal").textContent = (t / 100).toFixed(2);
  const pct = (x) => `${((100 * x) / n).toFixed(1)}% of rows`;
  $("#cm").innerHTML = `<div class="h"></div><div class="h">Predicted: not favourable</div><div class="h">Predicted: favourable</div>
    <div class="h">Truly not favourable</div><div class="c good"><div class="n">${fmtInt(tn)}</div><div class="d">true negatives · ${pct(tn)}</div></div><div class="c bad"><div class="n">${fmtInt(fp)}</div><div class="d">false alarms · ${pct(fp)}</div></div>
    <div class="h">Truly favourable</div><div class="c bad"><div class="n">${fmtInt(fn)}</div><div class="d">missed · ${pct(fn)}</div></div><div class="c good"><div class="n">${fmtInt(tp)}</div><div class="d">caught · ${pct(tp)}</div></div>`;
  const acc = (tp + tn) / n, pr = tp / (tp + fp || 1), rc = tp / (tp + fn), f1 = (2 * pr * rc) / (pr + rc || 1);
  $("#clfMetrics").innerHTML = [["accuracy", acc], ["precision", pr], ["recall", rc], ["F1", f1]].map(([k, v]) => `<div><b>${fmt(v, 3)}</b><span>${k}</span></div>`).join("");
  const rule = S.clf_sweep.climatology_rule;
  $("#clfNote").textContent = `At this threshold the model misses ${fmtInt(fn)} favourable cases. The climatology rule (long-term TCHP ≥ 60) misses ${fmtInt(rule[2])}.`;
  const pts = sw.tp_fp_fn_tn.map(([a, b, c, d]) => [b / (b + d), a / (a + c)]).reverse();
  const fpr = [0, ...pts.map((p) => p[0]), 1], tpr = [0, ...pts.map((p) => p[1]), 1];
  const C = S.classification, auc = C[clfModel].roc_auc;
  chart($("#rocChart"), { w: 480, h: 440, x: { min: 0, max: 1, ticks: [0, 0.2, 0.4, 0.6, 0.8, 1], label: "false positive rate (false alarms)" }, y: { min: 0, max: 1, ticks: [0, 0.2, 0.4, 0.6, 0.8, 1], label: "true positive rate (recall)" },
    series: [{ x: [0, 1], y: [0, 1], color: "rgba(22,25,31,.3)", dash: "3 4", width: 1 }, { x: fpr, y: tpr, color: "#214f4a", width: 2.4 }],
    marks: [{ x: rule[1] / (rule[1] + rule[3]), y: rule[0] / (rule[0] + rule[2]), color: "#16191f", type: "square", text: "climatology rule" }, { x: fp / (fp + tn), y: tp / (tp + fn), color: "#b4532a", stroke: "#f1ebe1", r: 7, text: `threshold ${(t / 100).toFixed(2)}` }],
    legend: [{ text: `${clfModel === "logistic_l1" ? "Logistic regression (L1)" : "Gradient boosting"} · AUC ${fmt(auc, 3)}`, color: "#214f4a" }], legendY: 360, legendX: 170,
    label: "ROC curve" });
}
function setupClf() {
  chipGroup($("#clfChips"), { logistic_l1: "Logistic regression (L1) · selected by CV", gradient_boosting: "Gradient boosting" }, clfModel, (k) => { clfModel = k; drawClf(); });
  $("#thr").addEventListener("input", drawClf); drawClf();
}

/* ------------------------------------------------------------------ boot */
(async function boot() {
  try {
    [META, S] = await Promise.all([fetch("data/meta.json").then((r) => r.json()), fetch("data/summary.json").then((r) => r.json())]);
  } catch (e) {
    document.body.insertAdjacentHTML("afterbegin", `<div style="position:fixed;z-index:99;inset:70px 20px auto;background:#b4532a;color:#fff;padding:14px;font:14px sans-serif">Data could not be loaded. If you opened index.html from disk, serve the folder instead (for example: python -m http.server).</div>`);
    return;
  }
  N = META.n_cells; CELLIDX = new Int32Array(NX * NY).fill(-1);
  META.cells.iy.forEach((y, i) => (CELLIDX[y * NX + META.cells.ix[i]] = i));
  const safe = (f) => { try { f(); } catch (e) { console.error(e); } };
  [setupNav, setupHero, setupStats, setupExplorer, setupDepth, setupArgo, setupCyclones, setupModels, setupClf].forEach(safe);
})();
