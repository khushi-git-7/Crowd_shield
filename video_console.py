"""The video console: a clean clip with the analysis drawn live on top of it, a side panel and a timeline.

Instead of burning dots and labels into the video, the browser draws them as the clip plays: each zone as a
soft area in the colour of its risk, a dot on every head counted at that second, and a small heads-up display.
Beside the video, each zone's count, fill and risk follow the playhead; under it, a timeline of every zone
with a playhead you can click to jump to any second. Everything comes from the same readings as before
(one per zone per second) and the head points kept at each count.
"""

from __future__ import annotations

import base64
import json

import streamlit.components.v1 as components

RISK = {"Safe": "#10b981", "Moderate": "#f59e0b", "High Risk": "#f97316", "Critical": "#ef4444",
        "Normal": "#10b981", "Crowded": "#f59e0b", "Dangerous": "#f97316", "Crush risk": "#ef4444"}
ZONE_COLOURS = ["#38bdf8", "#fb923c", "#34d399", "#a78bfa"]


def _clean(value):
    return None if isinstance(value, float) and value != value else value  # NaN -> null for JSON


def console_html(video: bytes, fps: float, size: tuple[int, int], zones: list[dict], rows: list[dict],
                 events: list[dict], points: list | None = None, count_every: int | None = None,
                 calibrated: bool = False) -> str:
    """The console as one HTML page. `zones`: [{"name", "polygon" [(x, y)...], "capacity"}], in the clip's
    pixels; `rows`: the monitor's readings; `points`: head points (x, y) at each count, every `count_every`
    frames."""
    data = {
        "fps": fps, "w": size[0], "h": size[1], "every": count_every or max(1, round(fps)),
        "calibrated": calibrated, "risk": RISK, "colours": ZONE_COLOURS,
        "zones": [{"name": z["name"], "poly": [[float(x), float(y)] for x, y in z["polygon"]],
                   "cap": z.get("capacity")} for z in zones],
        "rows": [{k: _clean(r.get(k)) for k in ("t", "zone", "people", "per_m2", "level")} for r in rows],
        "events": [{"t": e["t"], "text": e["event"].split(": ", 1)[-1]} for e in events],
        "points": points or [],
    }
    src = "data:video/mp4;base64," + base64.b64encode(video).decode()
    return (_TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__SRC__", src))


def show_console(video: bytes, fps: float, size: tuple[int, int], zones: list[dict], rows: list[dict],
                 events: list[dict], points: list | None = None, count_every: int | None = None,
                 calibrated: bool = False, height: int = 700) -> None:
    components.html(console_html(video, fps, size, zones, rows, events, points, count_every, calibrated),
                    height=height, scrolling=True)


_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
  :root { --bg:#0b1220; --panel:#111a2e; --line:#1e2a44; --text:#e2e8f0; --muted:#8a9bb8; --teal:#2dd4bf; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:Inter,system-ui,sans-serif; background:transparent; color:var(--text); overflow-x:hidden; }
  .console { background:var(--bg); border-radius:16px; padding:14px; border:1px solid var(--line); }
  .top { display:grid; grid-template-columns:minmax(0,1fr) 270px; gap:14px; }
  @media (max-width:760px) {  /* phones: video on top, the zones two by two under it */
    .top { grid-template-columns:minmax(0,1fr); }
    .console { padding:10px; }
    .console .panel { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:8px; }
    .zone .row { flex-wrap:wrap; gap:4px; }
    .console .panel .total { display:none; }
    .console .panel .status { grid-column:1 / -1; }
    .hud .txt { display:none; } .chip { padding:4px 9px; font-size:11px; }
    .zone { padding:9px 10px; } .zone .count { font-size:20px; } .sub { display:none; }
    .speed, #dots { display:none; }
    svg { height:110px; }
  }
  .stage { position:relative; border-radius:12px; overflow:hidden; background:#000; line-height:0; }
  video { width:100%; display:block; }
  canvas { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
  .hud { position:absolute; top:10px; left:10px; right:10px; display:flex; justify-content:space-between;
         pointer-events:none; line-height:1.2; }
  .chip { background:rgba(11,18,32,.72); backdrop-filter:blur(6px); border:1px solid rgba(255,255,255,.08);
          border-radius:999px; padding:5px 11px; font-size:12px; font-weight:600; display:flex; gap:8px;
          align-items:center; }
  .chip .mono { font-family:'JetBrains Mono',monospace; font-weight:700; }
  .rec { width:8px; height:8px; border-radius:50%; background:var(--teal); box-shadow:0 0 0 0 rgba(45,212,191,.7);
         animation:pulse 1.6s infinite; }
  @keyframes pulse { 0% { box-shadow:0 0 0 0 rgba(45,212,191,.6);} 70% { box-shadow:0 0 0 8px rgba(45,212,191,0);} 100% {} }
  .banner { position:absolute; left:10px; right:10px; bottom:54px; background:rgba(239,68,68,.92); color:#fff;
            border-radius:10px; padding:8px 12px; font-size:13px; font-weight:700; display:none; line-height:1.3; }
  .controls { display:flex; align-items:center; gap:10px; margin-top:10px; }
  button { font-family:inherit; background:var(--panel); color:var(--text); border:1px solid var(--line);
           border-radius:9px; padding:7px 12px; font-weight:600; font-size:13px; cursor:pointer; }
  button:hover { border-color:#334569; }
  button.play { background:var(--teal); color:#042f2e; border-color:var(--teal); min-width:84px; }
  .speed button.on { border-color:var(--teal); color:var(--teal); }
  .time { font-family:'JetBrains Mono',monospace; font-size:12.5px; color:var(--muted); margin-left:auto; }
  .panel { display:flex; flex-direction:column; gap:10px; }
  .total { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
  .label { font-size:10.5px; letter-spacing:.09em; text-transform:uppercase; color:var(--muted); font-weight:700; }
  .big { font-size:30px; font-weight:800; letter-spacing:-.02em; line-height:1.1; margin-top:4px;
         font-variant-numeric:tabular-nums; }
  .zone { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:11px 13px;
          border-left:4px solid var(--c); transition:border-color .3s; }
  .zone .row { display:flex; justify-content:space-between; align-items:center; gap:8px; }
  .zone .name { font-weight:700; font-size:14px; }
  .badge { font-size:10.5px; font-weight:800; letter-spacing:.06em; text-transform:uppercase; padding:3px 8px;
           border-radius:999px; background:color-mix(in srgb, var(--r) 18%, transparent); color:var(--r);
           white-space:nowrap; transition:all .3s; }
  .zone .count { font-size:24px; font-weight:800; margin:4px 0 6px; font-variant-numeric:tabular-nums; }
  .zone .count small { font-size:12px; color:var(--muted); font-weight:600; }
  .bar { height:6px; background:#1b2640; border-radius:99px; overflow:hidden; }
  .bar i { display:block; height:100%; width:0; background:var(--r); border-radius:99px; transition:width .35s, background .3s; }
  .sub { font-size:11.5px; color:var(--muted); margin-top:6px; }
  .status { border-radius:12px; padding:10px 12px; font-size:12.5px; font-weight:600; line-height:1.4; }
  .ok { background:rgba(16,185,129,.12); color:#6ee7b7; border:1px solid rgba(16,185,129,.25); }
  .alarm { background:rgba(239,68,68,.14); color:#fca5a5; border:1px solid rgba(239,68,68,.35); }
  .tl { margin-top:14px; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 12px 6px; }
  .tl .head { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }
  .legend { display:flex; gap:14px; font-size:12px; color:var(--muted); }
  .legend span { display:inline-flex; align-items:center; gap:6px; }
  .legend i { width:14px; height:3px; border-radius:2px; display:inline-block; }
  svg { width:100%; height:140px; display:block; cursor:pointer; }
</style></head><body>
<div class="console">
  <div class="top">
    <div>
      <div class="stage">
        <video id="v" src="__SRC__" playsinline muted preload="auto"></video>
        <canvas id="c"></canvas>
        <div class="hud">
          <div class="chip"><span class="rec"></span><span class="txt">Crowd Shield analysis</span> <span class="mono" id="clock">00:00.0</span></div>
          <div class="chip"><span id="hudTotal">0</span>&nbsp;people<span class="txt">&nbsp;in zones</span></div>
        </div>
        <div class="banner" id="banner"></div>
      </div>
      <div class="controls">
        <button class="play" id="play">&#9654; Play</button>
        <span class="speed"><button data-s="0.5">0.5×</button> <button data-s="1" class="on">1×</button> <button data-s="2">2×</button></span>
        <button id="dots">Dots: on</button>
        <span class="time" id="time"></span>
      </div>
    </div>
    <div class="panel" id="panel">
      <div class="total"><div class="label">In all zones now</div><div class="big" id="total">0</div>
        <div class="sub" id="peakAll"></div></div>
    </div>
  </div>
  <div class="tl">
    <div class="head"><div class="label">Each zone over time · click to jump</div><div class="legend" id="legend"></div></div>
    <svg id="chart"></svg>
  </div>
</div>
<script>
const D = __DATA__;
const v = document.getElementById('v'), cv = document.getElementById('c'), ctx = cv.getContext('2d');
const names = D.zones.map(z => z.name);
const colour = i => D.colours[i % D.colours.length];
const byZone = {}; names.forEach(n => byZone[n] = D.rows.filter(r => r.zone === n).sort((a, b) => a.t - b.t));
const duration = () => (isFinite(v.duration) && v.duration > 0) ? v.duration : Math.max(...D.rows.map(r => r.t), 1) + 1;
const fmt = s => { const m = Math.floor(s / 60), r = s - 60 * m; return String(m).padStart(2, '0') + ':' + r.toFixed(1).padStart(4, '0'); };
function level(r, cap) {
  if (D.calibrated) return r.level;
  if (!cap) return null; const s = r.people / cap;
  return s >= 1 ? 'Critical' : s >= .75 ? 'High Risk' : s >= .5 ? 'Moderate' : 'Safe';
}
function reading(name, t) {  // the latest reading at or before t
  const rs = byZone[name]; let out = rs[0];
  for (const r of rs) { if (r.t <= t + 1e-6) out = r; else break; }
  return out;
}
const peaks = {}; names.forEach(n => { const rs = byZone[n]; peaks[n] = rs.reduce((a, b) => b.people > a.people ? b : a, rs[0]); });

// ---- side panel
const panel = document.getElementById('panel'), cards = {};
D.zones.forEach((z, i) => {
  const el = document.createElement('div'); el.className = 'zone'; el.style.setProperty('--c', colour(i));
  el.innerHTML = `<div class="row"><span class="name">${z.name}</span><span class="badge"></span></div>
    <div class="count"><span class="n">0</span> <small>${D.calibrated ? 'per m²' : 'people'}</small></div>
    <div class="bar"><i></i></div><div class="sub"></div>`;
  panel.appendChild(el); cards[z.name] = el;
});
const status = document.createElement('div'); panel.appendChild(status);
const totals = {}; D.rows.forEach(r => totals[r.t] = (totals[r.t] || 0) + r.people);
const busiest = Object.entries(totals).reduce((a, b) => b[1] > a[1] ? b : a, ['0', 0]);
document.getElementById('peakAll').textContent = `busiest at ${(+busiest[0]).toFixed(0)} s: ${Math.round(busiest[1])} people`;

// ---- timeline
const svg = document.getElementById('chart'), NS = 'http://www.w3.org/2000/svg';
const legend = document.getElementById('legend');
D.zones.forEach((z, i) => legend.insertAdjacentHTML('beforeend', `<span><i style="background:${colour(i)}"></i>${z.name}</span>`));
let playhead, W = 0, H = 140, P = {l: 34, r: 8, t: 10, b: 22};
function value(r) { return D.calibrated ? (r.per_m2 || 0) : r.people; }
function drawChart() {
  W = svg.clientWidth; H = svg.clientHeight || 140; svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.innerHTML = '';
  const tMax = duration(), caps = D.calibrated ? [] : D.zones.map(z => z.cap || 0);
  const yMax = Math.max(...D.rows.map(value), ...caps, 1) * 1.12;
  const x = t => P.l + (W - P.l - P.r) * t / tMax, y = val => H - P.b - (H - P.t - P.b) * val / yMax;
  const add = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); svg.appendChild(e); return e; };
  for (let k = 0; k <= 4; k++) { const val = yMax * k / 4; add('line', {x1: P.l, x2: W - P.r, y1: y(val), y2: y(val), stroke: '#1e2a44'});
    add('text', {x: P.l - 6, y: y(val) + 4, 'text-anchor': 'end', fill: '#8a9bb8', 'font-size': 10}).textContent = Math.round(val); }
  const step = tMax > 30 ? 10 : tMax > 12 ? 2 : 1;
  for (let t = 0; t <= tMax; t += step) add('text', {x: x(t), y: H - 6, 'text-anchor': 'middle', fill: '#8a9bb8', 'font-size': 10}).textContent = t + ' s';
  D.events.forEach(e => add('rect', {x: x(e.t) - 2, y: P.t, width: 4, height: H - P.t - P.b, fill: '#ef4444', opacity: .8}));
  D.zones.forEach((z, i) => {
    if (!D.calibrated && z.cap) add('line', {x1: P.l, x2: W - P.r, y1: y(z.cap), y2: y(z.cap), stroke: colour(i), 'stroke-dasharray': '4 4', opacity: .55});
    const rs = byZone[z.name]; if (!rs.length) return;
    const pts = rs.map(r => [x(r.t), y(value(r))]);
    const area = `M${pts[0][0]},${y(0)} ` + pts.map(p => `L${p[0]},${p[1]}`).join(' ') + ` L${pts[pts.length - 1][0]},${y(0)} Z`;
    add('path', {d: area, fill: colour(i), opacity: .10});
    add('polyline', {points: pts.map(p => p.join(',')).join(' '), fill: 'none', stroke: colour(i), 'stroke-width': 2.2, 'stroke-linejoin': 'round'});
  });
  playhead = add('line', {x1: P.l, x2: P.l, y1: P.t - 4, y2: H - P.b, stroke: '#e2e8f0', 'stroke-width': 1.5});
  svg.onclick = ev => { const r = svg.getBoundingClientRect(), t = (ev.clientX - r.left - P.l) / (W - P.l - P.r) * tMax;
    v.currentTime = Math.min(Math.max(t, 0), tMax - 0.05); update(); };
}

// ---- overlay
let showDots = true;
function polyPath(poly, sx, sy) { ctx.beginPath(); poly.forEach(([px, py], k) => k ? ctx.lineTo(px * sx, py * sy) : ctx.moveTo(px * sx, py * sy)); ctx.closePath(); }
function pill(text, x0, y0, bg) {
  ctx.font = '600 12px Inter, sans-serif'; const w = ctx.measureText(text).width + 18, h = 22;
  ctx.fillStyle = bg; ctx.beginPath(); ctx.roundRect(x0, y0, w, h, 11); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.fillText(text, x0 + 9, y0 + 15);
}
function drawOverlay(t) {
  const r = v.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(r.width * dpr)) { cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr); }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, r.width, r.height);
  const sx = r.width / D.w, sy = r.height / D.h;
  const looks = D.zones.map((z, i) => { const rd = reading(z.name, t), lv = rd && level(rd, z.cap);
    return {rd, c: lv ? D.risk[lv] : colour(i)}; });
  D.zones.forEach((z, i) => {  // zone areas first, then the dots, then the labels on top
    polyPath(z.poly, sx, sy); ctx.fillStyle = looks[i].c + '22'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = looks[i].c; ctx.stroke();
  });
  if (showDots && D.points.length) {
    const k = Math.min(Math.floor(t * D.fps / D.every), D.points.length - 1), pts = D.points[Math.max(k, 0)] || [];
    const rad = Math.max(2.4, r.width / 260);
    ctx.lineWidth = 1;
    for (const [px, py] of pts) {
      ctx.beginPath(); ctx.arc(px * sx, py * sy, rad, 0, 6.2832);
      ctx.fillStyle = 'rgba(45,212,191,.85)'; ctx.fill(); ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.stroke();
    }
  }
  D.zones.forEach((z, i) => {
    const rd = looks[i].rd, xs = z.poly.map(p => p[0] * sx), ys = z.poly.map(p => p[1] * sy);
    const label = `${z.name} · ${rd ? (D.calibrated ? (rd.per_m2 || 0).toFixed(1) + '/m²' : Math.round(rd.people)) : '–'}`;
    pill(label, Math.min(...xs) + 8, Math.min(...ys) + 8, looks[i].c);
  });
}

// ---- tie it together
const banner = document.getElementById('banner');
function update() {
  const t = v.currentTime || 0;
  document.getElementById('clock').textContent = fmt(t);
  document.getElementById('time').textContent = fmt(t) + ' / ' + fmt(duration());
  let total = 0;
  D.zones.forEach((z, i) => {
    const rd = reading(z.name, t); if (!rd) return;
    const lv = level(rd, z.cap), c = lv ? D.risk[lv] : colour(i), el = cards[z.name];
    total += rd.people;
    el.style.setProperty('--r', c);
    el.querySelector('.n').textContent = D.calibrated ? (rd.per_m2 || 0).toFixed(1) : Math.round(rd.people);
    el.querySelector('.badge').textContent = lv || '';
    const share = D.calibrated ? Math.min((rd.per_m2 || 0) / 5, 1) : (z.cap ? Math.min(rd.people / z.cap, 1) : 0);
    el.querySelector('.bar i').style.width = (share * 100).toFixed(0) + '%';
    const pk = peaks[z.name];
    el.querySelector('.sub').textContent = (z.cap && !D.calibrated ? `holds ${z.cap} comfortably · ` : '') +
      `peak ${Math.round(pk.people)} at ${pk.t.toFixed(0)} s`;
  });
  document.getElementById('total').textContent = Math.round(total);
  document.getElementById('hudTotal').textContent = Math.round(total);
  const live = D.events.find(e => t >= e.t && t - e.t <= 2.5);
  banner.style.display = live ? 'block' : 'none'; if (live) banner.textContent = 'Surge alarm: ' + live.text;
  const fired = D.events.filter(e => e.t <= t);
  status.className = 'status ' + (D.events.length ? 'alarm' : 'ok');
  status.textContent = D.events.length ? `Surge alarm at ${D.events.map(e => e.t.toFixed(1) + ' s').join(', ')}` +
    (fired.length ? '' : ' (still to come)') : 'No surge: nobody suddenly started moving much faster than the crowd.';
  if (playhead) { const x = P.l + (W - P.l - P.r) * t / duration(); playhead.setAttribute('x1', x); playhead.setAttribute('x2', x); }
  drawOverlay(t);
}
function loop() { update(); if (!v.paused) requestAnimationFrame(loop); }
const play = document.getElementById('play');
play.onclick = () => v.paused ? v.play() : v.pause();
v.onplay = () => { play.innerHTML = '&#10074;&#10074; Pause'; loop(); };
v.onpause = () => { play.innerHTML = '&#9654; Play'; update(); };
v.onended = () => { play.innerHTML = '&#8635; Replay'; };
v.onseeked = update; v.onloadedmetadata = () => { drawChart(); update(); };
document.querySelectorAll('.speed button').forEach(b => b.onclick = () => {
  v.playbackRate = +b.dataset.s; document.querySelectorAll('.speed button').forEach(o => o.classList.toggle('on', o === b)); });
document.getElementById('dots').onclick = e => { showDots = !showDots; e.target.textContent = 'Dots: ' + (showDots ? 'on' : 'off'); update(); };
window.addEventListener('resize', () => { drawChart(); update(); });
drawChart(); update();
</script></body></html>"""
