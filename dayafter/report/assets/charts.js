"use strict";
/* Day After chart kit: dependency-free SVG charts for self-contained, offline reports.
   Conventions (docs/BRAND.md and the data-viz method): one y-axis per panel, 2 px lines, >= 8 px markers
   with a 2 px surface ring, solid hairline grid, text in ink tokens (never the series colour), a crosshair
   and tooltip on every time chart, one time cursor shared by all charts and the map. Colours are CSS
   variables, so switching the theme needs no re-render. Labels go in with textContent only. */
const DA = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const subs = new Map();
  let tipEl = null;
  let fHM = null, fDay = null;

  // ------------------------------------------------------------------ basics
  function setZone(tz) {
    fHM = new Intl.DateTimeFormat("en-AU", { timeZone: tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    fDay = new Intl.DateTimeFormat("en-AU", { timeZone: tz, weekday: "short", day: "numeric", month: "short" });
  }
  const hm = (t) => fHM.format(new Date(t * 1000));
  const dayLabel = (t) => fDay.format(new Date(t * 1000));
  function localMinutes(t) {
    const p = fHM.formatToParts(new Date(t * 1000));
    const h = +p.find((x) => x.type === "hour").value % 24;
    const m = +p.find((x) => x.type === "minute").value;
    return h * 60 + m;
  }
  const fin = (v) => typeof v === "number" && Number.isFinite(v);

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, s, attrs) {
    const t = el("text", Object.assign({ x, y }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  function paint(e, stroke, fill, extra) {
    if (stroke) e.style.stroke = stroke;
    e.style.fill = fill || "none";
    if (extra) Object.assign(e.style, extra);
    return e;
  }
  function linear(d0, d1, r0, r1) {
    const k = (r1 - r0) / (d1 - d0 || 1);
    const f = (v) => r0 + (v - d0) * k;
    f.invert = (p) => d0 + (p - r0) / k;
    f.lo = Math.min(r0, r1);
    f.hi = Math.max(r0, r1);
    return f;
  }
  function niceStep(span, n) {
    const raw = span / Math.max(1, n);
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;  // no 2.5 steps: whole-number ticks read better
  }
  function niceTicks(lo, hi, n) {
    if (!(hi > lo)) { lo -= 1; hi += 1; }
    const st = niceStep(hi - lo, n || 4);
    const a = Math.floor(lo / st + 1e-9) * st, b = Math.ceil(hi / st - 1e-9) * st;
    const out = [];
    for (let v = a; v <= b + st * 1e-6; v += st) out.push(+v.toFixed(6));
    return out;
  }
  function extent(arrays) {
    let lo = Infinity, hi = -Infinity;
    for (const a of arrays) if (a) for (const v of a) if (fin(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
    return lo <= hi ? [lo, hi] : null;
  }
  function timeTicks(t0, t1, width) {
    const pxPerHour = width / Math.max(1e-6, (t1 - t0) / 3600);
    const step = [1, 2, 3, 6, 12, 24].find((s) => s * pxPerHour >= 56) || 24;
    const start = Math.ceil(t0 / 60) * 60;
    const lm = localMinutes(start);
    const first = start + (((step * 60) - (lm % (step * 60))) % (step * 60)) * 60;
    const out = [];
    for (let t = first; t <= t1 + 1; t += step * 3600) out.push(t);
    return out;
  }
  function nearestIndex(sorted, t) {
    let lo = 0, hi = sorted.length - 1;
    if (hi < 0) return -1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (sorted[mid] < t) lo = mid; else hi = mid; }
    return Math.abs(sorted[lo] - t) <= Math.abs(sorted[hi] - t) ? lo : hi;
  }
  /* Position along a timed polyline at time t (linear between fixes), or null outside its span. */
  function along(ts, lat, lon, t) {
    const n = ts.length;
    if (n < 2 || t < ts[0] || t > ts[n - 1]) return null;
    let a = nearestIndex(ts, t);
    if (ts[a] > t) a -= 1;
    a = Math.max(0, Math.min(n - 2, a));
    const f = (t - ts[a]) / ((ts[a + 1] - ts[a]) || 1);
    return [lat[a] + f * (lat[a + 1] - lat[a]), lon[a] + f * (lon[a + 1] - lon[a])];
  }
  function lineKey(svgParent, color, dash, x, y, w) {
    const l = el("line", { x1: x, y1: y, x2: x + (w || 18), y2: y }, svgParent);
    paint(l, color, null, { strokeWidth: "2px", strokeDasharray: dash || "none", strokeLinecap: "round" });
    return l;
  }
  function marker(parent, shape, cx, cy, r, color) {
    let e;
    if (shape === "square") e = el("rect", { x: cx - r, y: cy - r, width: 2 * r, height: 2 * r, rx: 1 }, parent);
    else if (shape === "triangle") e = el("path", { d: `M${cx},${cy - r * 1.2}L${cx + r * 1.1},${cy + r * 0.8}L${cx - r * 1.1},${cy + r * 0.8}Z` }, parent);
    else if (shape === "diamond") e = el("path", { d: `M${cx},${cy - r * 1.3}L${cx + r * 1.1},${cy}L${cx},${cy + r * 1.3}L${cx - r * 1.1},${cy}Z` }, parent);
    else e = el("circle", { cx, cy, r }, parent);
    return paint(e, "var(--surface)", color, { strokeWidth: "2px" });
  }

  // ------------------------------------------------------------------ tooltip
  function tip() {
    if (!tipEl) {
      tipEl = document.createElement("div");
      tipEl.className = "tooltip";
      tipEl.setAttribute("role", "status");
      document.body.appendChild(tipEl);
    }
    return tipEl;
  }
  function showTip(clientX, clientY, head, rows) {
    const t = tip();
    t.textContent = "";
    const h = document.createElement("div");
    h.className = "tt-head";
    h.textContent = head;
    t.appendChild(h);
    for (const r of rows) {  // value leads (strong), the series name follows with its line key
      const row = document.createElement("div");
      row.className = "tt-row";
      const v = document.createElement("span");
      v.className = "v";
      v.textContent = r.value;
      const nm = document.createElement("span");
      nm.className = "nm";
      if (r.color) {
        const k = document.createElement("span");
        k.className = "line-key";
        k.style.borderTopColor = r.color;
        if (r.dash) k.style.borderTopStyle = "dashed";
        nm.appendChild(k);
      }
      nm.appendChild(document.createTextNode(r.name));
      row.appendChild(v);
      row.appendChild(nm);
      t.appendChild(row);
    }
    t.style.display = "block";
    const w = t.offsetWidth, hgt = t.offsetHeight;
    let x = clientX + 14, y = clientY + 14;
    if (x + w > window.innerWidth - 8) x = clientX - w - 14;
    if (y + hgt > window.innerHeight - 8) y = clientY - hgt - 14;
    t.style.left = Math.max(8, x) + "px";
    t.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { if (tipEl) tipEl.style.display = "none"; }

  // ------------------------------------------------------------------ shared time cursor
  let uid = 0;
  function subscribe(fn) { const id = ++uid; subs.set(id, fn); return id; }
  function emit(t, source) { for (const [id, fn] of subs) fn(t, source, id); }

  function mount(root, draw) {
    let pending = false, lastW = 0, subId = null;
    const redraw = () => {
      pending = false;
      const w = root.clientWidth;
      if (!w || w === lastW) return;
      lastW = w;
      if (subId !== null) subs.delete(subId);
      subId = draw();
    };
    redraw();
    if (window.ResizeObserver) new ResizeObserver(() => { if (!pending) { pending = true; requestAnimationFrame(redraw); } }).observe(root);
  }

  // ------------------------------------------------------------------ stacked time panels (meteogram)
  /* spec = {t0, t1, panels:[{label, height, domain?, minSpan?, ticks?, fmt?, series:[{name, t, y, y2?, kind:
     'line'|'dots'|'bars'|'band', color, dash?, width?}]}], vlines:[{t, label, strong?, dash?}], bands:[{t0, t1, label}],
     strip:{segments:[{t0, t1, text, kind}]}, snap:[t...], tip:(t)=>({head, rows}), aria} */
  function timePanels(root, spec) {
    root.textContent = "";
    const W = Math.max(300, root.clientWidth);
    const narrow = W < 520;
    const nLabels = (spec.vlines || []).filter((v) => v.label).length + (spec.bands || []).filter((b) => b.label).length;
    const m = { l: narrow ? 38 : 46, r: spec.endLabels ? 62 : 12, t: nLabels > 1 ? 40 : nLabels ? 28 : 8, b: 30 };
    const titleH = 16, gap = 10, stripH = spec.strip ? 24 : 0;
    const heights = spec.panels.map((p) => (p.height || 96) * (narrow ? 0.85 : 1));
    const H = m.t + heights.reduce((a, b) => a + b + titleH, 0) + gap * (spec.panels.length - 1) + (stripH ? stripH + gap : 0) + m.b;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "time chart" }, root);
    const x = linear(spec.t0, spec.t1, m.l, W - m.r);
    const bandLayer = el("g", null, svg);
    const plotTop = m.t;
    let yTop = m.t;
    const boxes = [];
    for (let i = 0; i < spec.panels.length; i++) {
      const p = spec.panels[i];
      const top = yTop + titleH, bottom = top + heights[i];
      text(svg, m.l, yTop + 11, p.label, { class: "t-ink", "font-size": 12 });
      let dom = p.domain;
      if (!dom) {
        const ext = extent(p.series.flatMap((s) => [s.y, s.y2]));
        dom = ext || [0, 1];
        if (p.zero) dom = [Math.min(0, dom[0]), dom[1]];
        const span = Math.max(dom[1] - dom[0], p.minSpan || 0);
        const mid = (dom[0] + dom[1]) / 2;
        if (dom[1] - dom[0] < span) dom = [mid - span / 2, mid + span / 2];
        if (p.zero) dom = [Math.max(0, dom[0]), dom[1]];
      }
      const ticks = p.ticks || niceTicks(dom[0], dom[1], heights[i] < 70 ? 2 : 3);
      const y = linear(ticks[0], ticks[ticks.length - 1], bottom, top);
      for (const v of ticks) {
        paint(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, svg), "var(--grid)", null, { strokeWidth: "1px" });
        text(svg, m.l - 6, y(v) + 4, p.fmt ? p.fmt(v) : String(v), { "text-anchor": "end" });
      }
      const g = el("g", null, svg);
      for (const s of p.series) drawSeries(g, s, x, y, bottom);
      if (spec.endLabels && i === 0) {  // direct labels at line ends (first panel); a colliding label is skipped, never stacked
        const used = [];
        for (const s of p.series) {
          if (!s.name || !s.y) continue;
          let k = s.y.length - 1;
          while (k >= 0 && !fin(s.y[k])) k--;
          if (k < 0) continue;
          const ly = y(s.y[k]);
          if (used.some((u) => Math.abs(u - ly) < 12)) continue;
          used.push(ly);
          lineKey(svg, s.color, s.dash, W - m.r + 4, ly, 10);
          text(svg, W - m.r + 17, ly + 4, s.name, { class: "t-ink" });
        }
      }
      boxes.push({ top, bottom, y, panel: p });
      yTop = bottom + gap;
    }
    const plotBottom = yTop - gap;
    if (spec.strip) {
      const top = plotBottom + gap;
      drawStrip(svg, spec.strip.segments, x, top, stripH);
      yTop = top + stripH + gap;
    }
    const axisY = (spec.strip ? yTop - gap : plotBottom) + 6;
    // bands (behind the data) and vertical markers (marks, ETA). All their labels share the top margin and
    // are placed by priority (strong first); a label that would collide is left to the tooltip.
    const labels = [];
    for (const b of spec.bands || []) {
      const x0 = Math.max(m.l, x(b.t0)), x1 = Math.min(W - m.r, x(b.t1));
      if (x1 <= x0) continue;
      paint(el("rect", { x: x0, y: plotTop, width: Math.max(2, x1 - x0), height: plotBottom - plotTop }, bandLayer), null, "var(--band)");
      if (b.label) labels.push({ px: (x0 + x1) / 2, text: b.label, strong: true, rank: 1 });
    }
    for (const v of spec.vlines || []) {
      const px = x(v.t);
      if (px < m.l - 0.5 || px > W - m.r + 0.5) continue;
      const vl = paint(el("line", { x1: px, x2: px, y1: plotTop - 4, y2: plotBottom }, svg), v.strong || v.dash ? "var(--ink)" : "var(--muted)", null,
        { strokeWidth: v.strong || v.dash ? "1.5px" : "1px", strokeOpacity: v.strong || v.dash ? 1 : 0.3 });
      if (v.dash) vl.setAttribute("stroke-dasharray", "5 4");
      if (v.label) labels.push({ px, text: v.label, strong: !!(v.strong || v.dash), rank: v.strong ? 0 : v.dash ? 1 : 2 });
    }
    const placed = [[], []];  // two label rows; the turning-mark label goes first, then bands, then the rest
    for (const lb of labels.sort((a, b) => a.rank - b.rank)) {
      const w = lb.text.length * 6.4 + 8;
      const lx = Math.min(Math.max(lb.px, m.l + w / 2), W - m.r - w / 2);
      const row = placed.findIndex((r, k) => (k === 0 || m.t >= 40) && !r.some((p) => Math.abs(p.x - lx) < (p.w + w) / 2));
      if (row < 0) continue;
      placed[row].push({ x: lx, w });
      text(svg, lx, plotTop - 8 - row * 13, lb.text, { "text-anchor": "middle", class: lb.strong ? "t-strong" : "" });
    }
    // x axis
    const ticks = timeTicks(spec.t0, spec.t1, W - m.l - m.r);
    let prevDay = null;
    for (const t of ticks) {
      const px = x(t);
      paint(el("line", { x1: px, x2: px, y1: axisY - 6, y2: axisY - 2 }, svg), "var(--muted)", null, { strokeWidth: "1px" });
      text(svg, px, axisY + 9, hm(t), { "text-anchor": "middle" });
      const d = dayLabel(t);
      if (d !== prevDay && (prevDay !== null || ticks.length && (spec.t1 - spec.t0) > 20 * 3600)) {
        text(svg, px, axisY + 21, d, { "text-anchor": "middle" });
      }
      prevDay = d;
    }
    // crosshair + tooltip
    const hair = paint(el("line", { x1: 0, x2: 0, y1: plotTop - 4, y2: plotBottom + (stripH ? stripH + gap : 0) }, svg), "var(--ink)", null,
      { strokeWidth: "1px", display: "none", pointerEvents: "none" });
    const dots = el("g", { "pointer-events": "none" }, svg);
    const hit = paint(el("rect", { x: m.l, y: plotTop - 4, width: W - m.l - m.r, height: axisY - plotTop }, svg), null, "transparent");
    const snapT = spec.snap && spec.snap.length ? spec.snap : null;
    function place(t) {
      dots.textContent = "";
      if (t === null || t < spec.t0 || t > spec.t1) { hair.style.display = "none"; return; }
      const px = x(t);
      hair.setAttribute("x1", px); hair.setAttribute("x2", px); hair.style.display = "";
      for (const b of boxes) for (const s of b.panel.series) {
        if (s.kind !== "line" || !s.t) continue;
        const k = nearestIndex(s.t, t);
        if (k >= 0 && fin(s.y[k]) && Math.abs(s.t[k] - t) < 1800) marker(dots, "circle", x(s.t[k]), b.y(s.y[k]), 4, s.color);
      }
    }
    const id = subscribe((t, src, me) => { place(t); });
    function onMove(ev) {
      const r = svg.getBoundingClientRect();
      const px = (ev.clientX - r.left) * (W / r.width);
      let t = x.invert(px);
      if (snapT) t = snapT[nearestIndex(snapT, t)];
      emit(t, id);
      if (spec.tip) { const c = spec.tip(t); showTip(ev.clientX, ev.clientY, c.head, c.rows); }
    }
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerdown", onMove);
    hit.addEventListener("pointerleave", () => { emit(null, id); hideTip(); });
    return id;
  }

  function drawSeries(g, s, x, y, baseline) {
    const t = s.t, v = s.y;
    if (!t || !v) return;
    if (s.kind === "band") {
      let d = "", started = false;
      const up = [], dn = [];
      for (let i = 0; i < t.length; i++) if (fin(v[i]) && fin(s.y2[i])) { up.push([x(t[i]), y(s.y2[i])]); dn.push([x(t[i]), y(v[i])]); }
      if (up.length > 1) {
        d = "M" + up.map((p) => p.join(",")).join("L") + "L" + dn.reverse().map((p) => p.join(",")).join("L") + "Z";
        paint(el("path", { d }, g), null, s.color, { fillOpacity: "0.1" });
      }
      return;
    }
    if (s.kind === "line") {
      let d = "", pen = false;
      for (let i = 0; i < t.length; i++) {
        if (!fin(v[i])) { pen = false; continue; }
        d += (pen ? "L" : "M") + x(t[i]).toFixed(1) + "," + y(v[i]).toFixed(1);
        pen = true;
      }
      paint(el("path", { d }, g), s.color, null, { strokeWidth: (s.width || 2) + "px", strokeDasharray: s.dash || "none",
        strokeLinejoin: "round", strokeLinecap: "round" });
      return;
    }
    if (s.kind === "dots") {
      if (s.dense) {  // many points: small solid dots, no surface ring (the rings would swallow each other)
        for (let i = 0; i < t.length; i++) if (fin(v[i])) paint(el("circle", { cx: x(t[i]), cy: y(v[i]), r: 1.8 }, g), null, s.color);
        return;
      }
      for (let i = 0; i < t.length; i++) if (fin(v[i])) marker(g, s.marker || "circle", x(t[i]), y(v[i]), 4, s.color);
      return;
    }
    if (s.kind === "bars") {
      const px = t.map(x);
      const gaps = [];
      for (let i = 1; i < px.length; i++) gaps.push(px[i] - px[i - 1]);
      gaps.sort((a, b) => a - b);
      const med = gaps.length ? gaps[gaps.length >> 1] : 12;  // median spacing: mark rows a minute apart must not shrink every bar
      const bw = Math.max(3, Math.min(24, med * 0.6));
      const y0 = y(0);
      for (let i = 0; i < t.length; i++) {
        if (!fin(v[i]) || v[i] <= 0) continue;
        const l = Math.max(x.lo, px[i] - bw / 2), rr = Math.min(x.hi, px[i] + bw / 2);  // stay inside the plot
        if (rr - l < 1) continue;
        const top = Math.min(y(v[i]), y0 - 1), r = Math.min(4, (rr - l) / 2, (y0 - top) / 2);
        const d = `M${l},${y0}V${top + r}Q${l},${top} ${l + r},${top}H${rr - r}Q${rr},${top} ${rr},${top + r}V${y0}Z`;
        paint(el("path", { d }, g), null, s.color);
      }
    }
  }

  function drawStrip(svg, segments, x, top, h) {
    const g = el("g", null, svg);
    for (const s of segments) {
      const x0 = x(s.t0) + 1, x1 = x(s.t1) - 1;
      if (x1 - x0 < 1) continue;
      paint(el("rect", { x: x0, y: top, width: x1 - x0, height: h, rx: 4 }, g), null, s.kind === "kite" ? "var(--sail-kite)" : "var(--sail-jib)");
      const t = text(g, (x0 + x1) / 2, top + h / 2 + 4, s.text, { "text-anchor": "middle", class: "t-ink" });
      if (t.getComputedTextLength() > x1 - x0 - 6) t.remove();
    }
  }

  // ------------------------------------------------------------------ rows on a time axis (window, sails)
  /* spec = {t0, t1, rows:[{label, key:{color, dash}, segments:[{t0, t1, text, kind}], marks:[{t, shape, color, label}],
     tip?:(t)=>[rows]}], bands:[{t0, t1, label}], vlines:[{t, label}], rowH, head?:(t)=>string, aria} */
  function timeRows(root, spec) {
    root.textContent = "";
    const W = Math.max(300, root.clientWidth);
    const labelW = Math.min(110, Math.max(64, ...spec.rows.map((r) => r.label.length * 7.4 + 28)));
    const m = { l: labelW, r: 14, t: (spec.vlines && spec.vlines.length) || (spec.bands || []).some((b) => b.label) ? 24 : 8, b: 30 };
    const rowH = spec.rowH || 38;
    const H = m.t + rowH * spec.rows.length + m.b;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "timeline" }, root);
    const x = linear(spec.t0, spec.t1, m.l, W - m.r);
    const bottom = m.t + rowH * spec.rows.length;
    for (const b of spec.bands || []) {
      const x0 = Math.max(m.l, x(b.t0)), x1 = Math.min(W - m.r, x(b.t1));
      if (x1 <= x0) continue;
      paint(el("rect", { x: x0, y: m.t, width: Math.max(2, x1 - x0), height: bottom - m.t }, svg), null, "var(--band)");
      if (b.label) text(svg, (x0 + x1) / 2, m.t - 8, b.label, { "text-anchor": "middle", class: "t-strong" });
    }
    const ticks = timeTicks(spec.t0, spec.t1, W - m.l - m.r);
    for (const t of ticks) {
      const px = x(t);
      paint(el("line", { x1: px, x2: px, y1: m.t, y2: bottom }, svg), "var(--grid)", null, { strokeWidth: "1px" });
      text(svg, px, bottom + 16, hm(t), { "text-anchor": "middle" });
    }
    for (const v of spec.vlines || []) {
      const px = x(v.t);
      if (px < m.l || px > W - m.r) continue;
      paint(el("line", { x1: px, x2: px, y1: m.t - 4, y2: bottom }, svg), "var(--ink)", null, { strokeWidth: "1px" });
      if (v.label) text(svg, px, m.t - 8, v.label, { "text-anchor": px > W - 80 ? "end" : "middle", class: "t-strong" });
    }
    spec.rows.forEach((r, i) => {
      const cy = m.t + rowH * i + rowH / 2;
      if (r.key) lineKey(svg, r.key.color, r.key.dash, 4, cy, 14);
      text(svg, r.key ? 24 : 4, cy + 4, r.label, { class: "t-ink", "font-size": 12 });
      paint(el("line", { x1: m.l, x2: W - m.r, y1: m.t + rowH * (i + 1), y2: m.t + rowH * (i + 1) }, svg), "var(--grid)", null, { strokeWidth: "1px" });
      const topLane = (r.marks || []).some((mk) => mk.top);
      if (r.segments && r.segments.length) drawStrip(svg, r.segments, x, topLane ? cy - 5 : cy - 11, topLane ? 18 : 22);
      const lanes = { above: [], below: [] };  // label lanes per row; a label that would collide is dropped
      for (const mk of r.marks || []) {
        const px = x(mk.t);
        if (px < m.l - 4 || px > W - m.r + 4) continue;
        marker(svg, mk.shape || "circle", px, mk.top ? cy - 12 : cy, mk.r || 5, mk.color || "var(--ink)");
        if (!mk.label) continue;
        const w = mk.label.length * 6.4, right = px < W - 70;
        const x0 = right ? px + 8 : px - 8 - w, x1 = x0 + w;
        const lane = lanes[mk.below ? "below" : "above"];
        if (lane.some(([a, b]) => x0 < b + 4 && x1 > a - 4)) continue;
        lane.push([x0, x1]);
        text(svg, right ? px + 8 : px - 8, mk.below ? cy + 16 : cy - 8, mk.label, { "text-anchor": right ? "start" : "end" });
      }
    });
    const hair = paint(el("line", { x1: 0, x2: 0, y1: m.t, y2: bottom }, svg), "var(--ink)", null, { strokeWidth: "1px", display: "none", pointerEvents: "none" });
    const hit = paint(el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: bottom - m.t }, svg), null, "transparent");
    const id = subscribe((t) => {
      if (t === null || t < spec.t0 || t > spec.t1) { hair.style.display = "none"; return; }
      hair.setAttribute("x1", x(t)); hair.setAttribute("x2", x(t)); hair.style.display = "";
    });
    function onMove(ev) {
      const r = svg.getBoundingClientRect();
      const t = x.invert((ev.clientX - r.left) * (W / r.width));
      emit(t, id);
      const rows = [];
      for (const row of spec.rows) for (const it of row.tip ? row.tip(t) : []) rows.push(it);
      if (rows.length) showTip(ev.clientX, ev.clientY, spec.head ? spec.head(t) : hm(t), rows); else hideTip();
    }
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerdown", onMove);
    hit.addEventListener("pointerleave", () => { emit(null, id); hideTip(); });
    return id;
  }

  // ------------------------------------------------------------------ map
  /* spec = {land:[[[lon,lat]...]...], coast:[[[lon,lat]...]...], islands:[{name, lat:[], lon:[]}],
     routes:[{name, color, dash, marker, t:[], lat:[], lon:[], info:(i)=>[rows]}], marks:[{name, lat, lon, role}],
     points:[{lat, lon, shape, color, label}], attribution, aria} */
  function map(root, spec) {
    root.textContent = "";
    root.classList.add("map");
    const W = Math.max(300, root.clientWidth);
    const H = Math.round(Math.min(560, Math.max(320, W * 0.72)));
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "map" }, root);
    svg.style.overflow = "hidden";
    svg.style.background = "var(--surface)";
    const lats = [], lons = [];
    for (const r of spec.routes) { lats.push(...r.lat); lons.push(...r.lon); }
    for (const mk of spec.marks || []) { lats.push(mk.lat); lons.push(mk.lon); }
    const [la0, la1] = extent([lats]) || [-34, -33];
    const [lo0, lo1] = extent([lons]) || [151, 152];
    const lat0 = (la0 + la1) / 2, lon0 = (lo0 + lo1) / 2, kx = Math.cos((lat0 * Math.PI) / 180);
    const P = (lat, lon) => [(lon - lon0) * kx, -(lat - lat0)];
    const spanX = Math.max(0.02, (lo1 - lo0) * kx), spanY = Math.max(0.02, la1 - la0);
    const fit = Math.min((W * 0.86) / spanX, (H * 0.86) / spanY);
    const view = { cx: 0, cy: 0, s: fit };
    const S = (lat, lon) => { const [X, Y] = P(lat, lon); return [W / 2 + (X - view.cx) * view.s, H / 2 + (Y - view.cy) * view.s]; };
    const gBase = el("g", null, svg), gOver = el("g", null, svg), gCursor = el("g", { "pointer-events": "none" }, svg);
    const hover = [];
    let cursorT = null;

    function ringPath(ring) {
      let d = "";
      for (let i = 0; i < ring.length; i++) { const p = S(ring[i][1], ring[i][0]); d += (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); }
      return d;
    }
    function render() {
      gBase.textContent = ""; gOver.textContent = ""; hover.length = 0;
      if (spec.land && spec.land.length) paint(el("path", { d: spec.land.map((r) => ringPath(r) + "Z").join(""), "fill-rule": "evenodd" }, gBase), null, "var(--land)");
      if (spec.coast && spec.coast.length && view.s > fit * 1.5) paint(el("path", { d: spec.coast.map(ringPath).join("") }, gBase), "var(--coast)", null, { strokeWidth: "1px" });
      for (const isl of spec.islands || []) {
        const ring = isl.lat.map((la, i) => [isl.lon[i], la]);
        paint(el("path", { d: ringPath(ring) + "Z" }, gBase), "var(--coast)", "var(--land)", { strokeWidth: "1px" });
      }
      for (const r of spec.routes) {
        let d = "", pen = false;
        for (let i = 0; i < r.lat.length; i++) {  // a missing fix (GPS dropout) breaks the line
          if (!fin(r.lat[i]) || !fin(r.lon[i])) { pen = false; continue; }
          const p = S(r.lat[i], r.lon[i]);
          d += (pen ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1);
          pen = true;
          hover.push({ x: p[0], y: p[1], route: r, i });
        }
        paint(el("path", { d }, gBase), r.color, null,
          { strokeWidth: (r.width || 2) + "px", strokeDasharray: r.dash || "none", strokeLinejoin: "round", strokeOpacity: r.opacity || 1 });
        if (r.hourly === false) continue;
        for (let t = Math.ceil(r.t[0] / 3600) * 3600; t <= r.t[r.t.length - 1]; t += 3600) {  // a marker every full hour
          const q = along(r.t, r.lat, r.lon, t);
          if (q && fin(q[0]) && fin(q[1])) { const p = S(q[0], q[1]); marker(gOver, r.marker, p[0], p[1], 4, r.color); }
        }
      }
      const labelled = [];  // label boxes already placed; a label that would overlap one is left out
      const place = (px, py, s, attrs) => {
        const w = s.length * 6.4, box = [px, py - 11, px + w, py + 3];
        if (labelled.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) return;
        labelled.push(box);
        text(gOver, px, py, s, attrs);
      };
      for (const mk of spec.marks || []) {
        const [px, py] = S(mk.lat, mk.lon);
        const strong = mk.role === "turning_mark" || mk.role === "start" || mk.role === "finish";
        paint(el("path", { d: `M${px - 4},${py - 4}L${px + 4},${py + 4}M${px - 4},${py + 4}L${px + 4},${py - 4}` }, gOver), "var(--ink)", null, { strokeWidth: strong ? "2px" : "1.5px" });
        if (strong || view.s > fit * 2.5) place(px + 7, py - 6, mk.name, { class: strong ? "t-strong" : "" });
      }
      for (const pt of spec.points || []) {
        const [px, py] = S(pt.lat, pt.lon);
        marker(gOver, pt.shape || "diamond", px, py, 6, pt.color);
        if (pt.label) place(px + 9, py + 4, pt.label, {});
      }
      const nmPerPx = 60 / view.s;  // one projected unit is one degree of latitude = 60 nm
      const nice = [0.5, 1, 2, 5, 10, 20, 50, 100].find((v) => v >= nmPerPx * 60) || 100;
      const len = nice / nmPerPx;
      paint(el("path", { d: `M12,${H - 18}V${H - 12}H${12 + len}V${H - 18}` }, gOver), "var(--ink-2)", null, { strokeWidth: "1.5px" });
      text(gOver, 12 + len + 6, H - 12, `${nice} nm`);
      text(gOver, 18, 24, "N", { "text-anchor": "middle", class: "t-strong" });
      paint(el("path", { d: "M18,28L14,40L18,37L22,40Z" }, gOver), null, "var(--ink-2)");
      if (spec.attribution) text(gOver, W - 8, H - 8, spec.attribution, { "text-anchor": "end", "font-size": 10 });
      drawCursor();
    }
    function drawCursor() {
      gCursor.textContent = "";
      if (cursorT === null) return;
      for (const r of spec.routes) {
        const q = along(r.t, r.lat, r.lon, cursorT);
        if (q && fin(q[0]) && fin(q[1])) { const p = S(q[0], q[1]); marker(gCursor, "circle", p[0], p[1], 6, r.color); }
      }
    }
    render();
    const id = subscribe((t) => { cursorT = t; drawCursor(); });

    // Mouse: drag pans; the wheel zooms once the map is active (clicked) or with Ctrl/Cmd, so the page
    // still scrolls past it. Touch: one finger scrolls the page, two fingers pinch and pan the map.
    const ptrs = new Map();
    let gesture = null, active = false, frame = false;
    const toView = (ev) => { const r = svg.getBoundingClientRect(); return [(ev.clientX - r.left) * (W / r.width), (ev.clientY - r.top) * (H / r.height)]; };
    const schedule = () => { if (!frame) { frame = true; requestAnimationFrame(() => { frame = false; render(); }); } };
    function zoomAt(px, py, factor) {
      const s1 = Math.max(fit * 0.5, Math.min(fit * 80, view.s * factor));
      const X = view.cx + (px - W / 2) / view.s, Y = view.cy + (py - H / 2) / view.s;
      view.s = s1;
      view.cx = X - (px - W / 2) / view.s;
      view.cy = Y - (py - H / 2) / view.s;
      schedule();
    }
    function hoverAt(ev, p) {
      let best = null, bd = 24 * 24;
      for (const h of hover) { const d = (h.x - p[0]) ** 2 + (h.y - p[1]) ** 2; if (d < bd) { bd = d; best = h; } }
      if (best) {
        emit(best.route.t[best.i], id);
        showTip(ev.clientX, ev.clientY, `${best.route.name} · ${hm(best.route.t[best.i])}`, best.route.info ? best.route.info(best.i) : []);
      } else { emit(null, id); hideTip(); }
    }
    svg.addEventListener("wheel", (ev) => {
      if (!(active || ev.ctrlKey || ev.metaKey)) return;
      ev.preventDefault();
      const [px, py] = toView(ev);
      zoomAt(px, py, ev.deltaY < 0 ? 1.25 : 0.8);
    }, { passive: false });
    svg.addEventListener("pointerdown", (ev) => {
      active = true;
      ptrs.set(ev.pointerId, toView(ev));
      if (ev.pointerType === "mouse" || ptrs.size === 2) svg.setPointerCapture(ev.pointerId);
      if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()];
        gesture = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), mx: (a[0] + b[0]) / 2, my: (a[1] + b[1]) / 2 };
      } else if (ev.pointerType !== "mouse") hoverAt(ev, toView(ev));
    });
    const lift = (ev) => { ptrs.delete(ev.pointerId); if (ptrs.size < 2) gesture = null; };
    svg.addEventListener("pointerup", lift);
    svg.addEventListener("pointercancel", lift);
    svg.addEventListener("pointermove", (ev) => {
      const p = toView(ev);
      if (gesture && ptrs.has(ev.pointerId)) {
        ptrs.set(ev.pointerId, p);
        const [a, b] = [...ptrs.values()];
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]), mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
        view.cx -= (mx - gesture.mx) / view.s; view.cy -= (my - gesture.my) / view.s;
        zoomAt(mx, my, d / (gesture.d || d));
        gesture = { d, mx, my };
        hideTip();
        return;
      }
      if (ev.pointerType === "mouse" && ptrs.has(ev.pointerId) && (ev.buttons & 1)) {
        const q = ptrs.get(ev.pointerId);
        view.cx -= (p[0] - q[0]) / view.s; view.cy -= (p[1] - q[1]) / view.s;
        ptrs.set(ev.pointerId, p);
        schedule();
        hideTip();
        return;
      }
      hoverAt(ev, p);
    });
    svg.addEventListener("pointerleave", () => { active = false; emit(null, id); hideTip(); });
    const tools = document.createElement("div");  // below the map, so the buttons never cover the course
    tools.className = "map-tools";
    for (const [label, title, fn] of [["+", "Zoom in", () => zoomAt(W / 2, H / 2, 1.5)], ["−", "Zoom out", () => zoomAt(W / 2, H / 2, 1 / 1.5)],
      ["Reset", "Show the whole course", () => { view.cx = 0; view.cy = 0; view.s = fit; schedule(); }]]) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = label; b.title = title; b.setAttribute("aria-label", title);
      b.addEventListener("click", fn);
      tools.appendChild(b);
    }
    root.appendChild(tools);
    return id;
  }

  // ------------------------------------------------------------------ x-y lines (e.g. minutes vs distance)
  /* spec = {x0, x1, xTicks?:[{x, label}], xFmt?, yLabel, yFmt?, zero?, height?, series:[{name, x:[], y:[], color,
     dash?, marker?}], vlines:[{x, label}], snap:[x...], tip:(k)=>({head, rows}), endLabels?, y0?, y1? (domain at
     least this wide), ref? (a y value drawn as a stronger grid line, e.g. 100 %), aria} */
  function xyLines(root, spec) {
    root.textContent = "";
    const W = Math.max(300, root.clientWidth);
    const H = spec.height || 300;
    const m = { l: 50, r: spec.endLabels ? 96 : 14, t: (spec.vlines || []).some((v) => v.label) ? 26 : 12, b: 34 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "chart" }, root);
    const x = linear(spec.x0, spec.x1, m.l, W - m.r);
    const ext = extent(spec.series.map((s) => s.y)) || [0, 1];
    let lo = spec.zero ? Math.min(0, ext[0]) : ext[0], hi = spec.zero ? Math.max(0, ext[1]) : ext[1];
    if (fin(spec.y0)) lo = Math.min(lo, spec.y0);
    if (fin(spec.y1)) hi = Math.max(hi, spec.y1);
    const ticks = niceTicks(lo, hi, 5);
    const y = linear(ticks[0], ticks[ticks.length - 1], H - m.b, m.t);
    for (const v of ticks) {
      paint(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, svg), (v === 0 && spec.zero) || v === spec.ref ? "var(--ink-2)" : "var(--grid)", null,
        { strokeWidth: "1px" });
      text(svg, m.l - 6, y(v) + 4, spec.yFmt ? spec.yFmt(v) : String(v), { "text-anchor": "end" });
    }
    if (spec.yLabel) text(svg, m.l, m.t - 10 > 8 ? 10 : m.t - 2, spec.yLabel, { class: "t-ink", "font-size": 12 });
    const xt = spec.xTicks || niceTicks(spec.x0, spec.x1, 6).map((v) => ({ x: v, label: spec.xFmt ? spec.xFmt(v) : String(v) }));
    let lastX = -Infinity;
    for (const tk of xt) {
      const px = x(tk.x);
      if (px < m.l - 1 || px > W - m.r + 1) continue;
      paint(el("line", { x1: px, x2: px, y1: H - m.b, y2: H - m.b + 4 }, svg), "var(--muted)", null, { strokeWidth: "1px" });
      if (px - lastX > tk.label.length * 6.4 + 8) { text(svg, px, H - m.b + 16, tk.label, { "text-anchor": "middle" }); lastX = px; }
    }
    if (spec.xLabel) text(svg, (m.l + W - m.r) / 2, H - 4, spec.xLabel, { "text-anchor": "middle" });
    for (const v of spec.vlines || []) {
      const px = x(v.x);
      paint(el("line", { x1: px, x2: px, y1: m.t - 4, y2: H - m.b }, svg), "var(--muted)", null, { strokeWidth: "1px" });
      if (v.label) text(svg, px, m.t - 8, v.label, { "text-anchor": "middle", class: "t-strong" });
    }
    const used = [];
    for (const s of spec.series) {
      let d = "", pen = false;
      for (let i = 0; i < s.x.length; i++) {
        if (!fin(s.y[i])) { pen = false; continue; }
        d += (pen ? "L" : "M") + x(s.x[i]).toFixed(1) + "," + y(s.y[i]).toFixed(1);
        pen = true;
      }
      paint(el("path", { d }, svg), s.color, null, { strokeWidth: "2px", strokeDasharray: s.dash || "none", strokeLinejoin: "round" });
      for (let i = 0; i < s.x.length; i++) if (fin(s.y[i])) marker(svg, s.marker || "circle", x(s.x[i]), y(s.y[i]), 4, s.color);
      if (spec.endLabels) {
        let k = s.y.length - 1;
        while (k >= 0 && !fin(s.y[k])) k--;
        if (k >= 0 && !used.some((u) => Math.abs(u - y(s.y[k])) < 13)) {
          used.push(y(s.y[k]));
          text(svg, x(s.x[k]) + 10, y(s.y[k]) + 4, `${s.name} ${spec.endFmt ? spec.endFmt(s.y[k]) : s.y[k]}`, { class: "t-ink" });
        }
      }
    }
    const hair = paint(el("line", { x1: 0, x2: 0, y1: m.t, y2: H - m.b }, svg), "var(--ink)", null, { strokeWidth: "1px", display: "none", pointerEvents: "none" });
    const hit = paint(el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }, svg), null, "transparent");
    const snap = spec.snap || [];
    function onMove(ev) {
      if (!snap.length) return;
      const r = svg.getBoundingClientRect();
      const k = nearestIndex(snap, x.invert((ev.clientX - r.left) * (W / r.width)));
      hair.setAttribute("x1", x(snap[k])); hair.setAttribute("x2", x(snap[k])); hair.style.display = "";
      if (spec.tip) { const c = spec.tip(k); showTip(ev.clientX, ev.clientY, c.head, c.rows); }
    }
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerdown", onMove);
    hit.addEventListener("pointerleave", () => { hair.style.display = "none"; hideTip(); });
    return null;
  }

  // ------------------------------------------------------------------ scatter
  /* spec = {x0, x1, xFmt, xTicks?, yLabel, yFmt?, xLabel, height?, points:[{x, y, color, shape?, r?, label?, tip:[rows],
     head}], aria}. Points are drawn in order (context first, emphasised last); labelled points get direct labels. */
  function scatter(root, spec) {
    root.textContent = "";
    const W = Math.max(300, root.clientWidth), H = spec.height || 300;
    const m = { l: 50, r: 16, t: 14, b: 36 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": spec.aria || "scatter" }, root);
    const x = linear(spec.x0, spec.x1, m.l, W - m.r);
    const ext = extent([spec.points.map((p) => p.y)]) || [0, 1];
    const yt = niceTicks(ext[0], ext[1], 5);
    const y = linear(yt[0], yt[yt.length - 1], H - m.b, m.t);
    for (const v of yt) {
      paint(el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, svg), "var(--grid)", null, { strokeWidth: "1px" });
      text(svg, m.l - 6, y(v) + 4, spec.yFmt ? spec.yFmt(v) : String(v), { "text-anchor": "end" });
    }
    if (spec.yLabel) text(svg, m.l, 10, spec.yLabel, { class: "t-ink", "font-size": 12 });
    for (const tk of spec.xTicks || []) {
      const px = x(tk.x);
      paint(el("line", { x1: px, x2: px, y1: H - m.b, y2: H - m.b + 4 }, svg), "var(--muted)", null, { strokeWidth: "1px" });
      text(svg, px, H - m.b + 16, tk.label, { "text-anchor": "middle" });
    }
    if (spec.xLabel) text(svg, (m.l + W - m.r) / 2, H - 4, spec.xLabel, { "text-anchor": "middle" });
    const pts = spec.points.map((p) => ({ p, px: x(p.x), py: y(p.y) }));
    for (const q of pts) marker(svg, q.p.shape || "circle", q.px, q.py, q.p.r || 4, q.p.color);
    const placed = [];
    for (const q of pts) {
      if (!q.p.label) continue;
      const w = q.p.label.length * 6.4, right = q.px < W - w - 20;
      const box = [right ? q.px + 8 : q.px - 8 - w, q.py - 12, right ? q.px + 8 + w : q.px - 8, q.py + 2];
      if (placed.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
      placed.push(box);
      text(svg, right ? q.px + 8 : q.px - 8, q.py - 2, q.p.label, { "text-anchor": right ? "start" : "end", class: "t-ink" });
    }
    const hit = paint(el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }, svg), null, "transparent");
    const ring = paint(el("circle", { cx: 0, cy: 0, r: 8 }, svg), "var(--ink)", null, { strokeWidth: "1.5px", display: "none", pointerEvents: "none" });
    function onMove(ev) {
      const r = svg.getBoundingClientRect();
      const mx = (ev.clientX - r.left) * (W / r.width), my = (ev.clientY - r.top) * (H / r.height);
      let best = null, bd = 24 * 24;
      for (const q of pts) { const d = (q.px - mx) ** 2 + (q.py - my) ** 2; if (d < bd) { bd = d; best = q; } }
      if (!best) { ring.style.display = "none"; hideTip(); return; }
      ring.setAttribute("cx", best.px); ring.setAttribute("cy", best.py); ring.style.display = "";
      showTip(ev.clientX, ev.clientY, best.p.head || "", best.p.tip || []);
    }
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerdown", onMove);
    hit.addEventListener("pointerleave", () => { ring.style.display = "none"; hideTip(); });
    return null;
  }

  // ------------------------------------------------------------------ legend (HTML)
  function legend(host, items) {
    host.textContent = "";
    host.classList.add("legend");
    for (const it of items) {
      const span = document.createElement("span");
      span.className = "key";
      const s = document.createElementNS(NS, "svg");
      s.setAttribute("viewBox", "0 0 22 10");
      if (it.kind === "rect") paint(el("rect", { x: 2, y: 1, width: 18, height: 8, rx: 2 }, s), null, it.color);
      else if (it.kind === "dot") marker(s, it.marker || "circle", 11, 5, 4, it.color);
      else {
        lineKey(s, it.color, it.dash, 2, 5, 18);
        if (it.marker) marker(s, it.marker, 11, 5, 3.5, it.color);
      }
      span.appendChild(s);
      span.appendChild(document.createTextNode(it.label));
      host.appendChild(span);
    }
  }

  // ------------------------------------------------------------------ wind-direction axis
  /* A 360° axis centred on the prevailing direction (vector mean, rounded to 90°), so a northerly does not flip
     between the top and the bottom of the panel. Returns {domain, ticks, fmt, wrap}; wrap() maps values onto it. */
  function dirAxis(...lists) {
    let sx = 0, sy = 0;
    for (const list of lists) for (const v of list || []) if (fin(v)) { sx += Math.sin(v * Math.PI / 180); sy += Math.cos(v * Math.PI / 180); }
    const mean = (Math.atan2(sx, sy) * 180 / Math.PI + 360) % 360;
    const c = (sx === 0 && sy === 0) ? 180 : (Math.round(mean / 90) * 90) % 360;
    const lo = c - 180;
    const names = { 0: "N", 90: "E", 180: "S", 270: "W" };
    return {
      domain: [lo, lo + 360], ticks: [lo, lo + 90, lo + 180, lo + 270, lo + 360],
      fmt: (v) => names[((v % 360) + 360) % 360],
      wrap: (v) => (fin(v) ? c + ((((v - c) % 360) + 540) % 360) - 180 : v),
    };
  }

  // ------------------------------------------------------------------ model styles (BRAND §2)
  // GFS, ECMWF and ACCESS own a colour each (validated all-pairs); any other model is neutral grey and is told
  // apart by its dash, marker and a direct label.
  const MODEL = {
    GFS: { color: "var(--m-gfs)", dash: "6 3", marker: "circle" },
    ECMWF: { color: "var(--m-ecmwf)", dash: "2 2", marker: "square" },
    ACCESS: { color: "var(--m-access)", dash: "8 3 2 3", marker: "triangle" },
  };
  const OTHER_DASH = ["4 2", "1 3", "10 3", "3 3 1 3"];
  const otherIx = new Map();
  function modelStyle(m) {
    if (MODEL[m]) return MODEL[m];
    if (!otherIx.has(m)) otherIx.set(m, otherIx.size);
    return { color: "var(--m-other)", dash: OTHER_DASH[otherIx.get(m) % OTHER_DASH.length], marker: "diamond" };
  }

  // ------------------------------------------------------------------ theme button: auto -> light -> dark
  function themeButton(btn) {
    if (!btn) return;
    const get = () => { try { return localStorage.getItem("da-theme"); } catch (e) { return null; } };
    const set = (v) => { try { if (v) localStorage.setItem("da-theme", v); else localStorage.removeItem("da-theme"); } catch (e) { /* private mode */ } };
    const apply = (v) => {
      if (v) document.documentElement.setAttribute("data-theme", v); else document.documentElement.removeAttribute("data-theme");
      btn.textContent = v === "dark" ? "Theme: dark" : v === "light" ? "Theme: light" : "Theme: auto";
    };
    apply(get());
    btn.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme");
      const next = cur === null ? "light" : cur === "light" ? "dark" : null;
      set(next); apply(next);
    });
  }

  return { setZone, hm, dayLabel, mount, timePanels, timeRows, xyLines, scatter, map, legend, emit, fin, nearest: nearestIndex, themeButton, dirAxis, modelStyle };
})();
