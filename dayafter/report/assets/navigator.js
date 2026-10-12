"use strict";
/* Navigator edition (Day After): charts from the embedded race data (see report/navigator.py).
   Our boat is always blue (--boat); each model keeps its fixed colour, dash and marker. */
(function () {
  const D = JSON.parse(document.getElementById("da-data").textContent);
  DA.setZone(D.tz);
  DA.themeButton(document.querySelector(".theme-btn"));
  const fin = DA.fin, hm = DA.hm;
  const STYLE = {
    GFS: { color: "var(--m-gfs)", dash: "6 3", marker: "circle" },
    ECMWF: { color: "var(--m-ecmwf)", dash: "2 2", marker: "square" },
    ACCESS: { color: "var(--m-access)", dash: "8 3 2 3", marker: "triangle" },
  };
  const style = (m) => STYLE[m] || { color: "var(--m-other)", dash: null, marker: "diamond" };
  const BOAT = "var(--boat)";
  const COMPASS = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split(" ");
  const compass = (d) => (fin(d) ? COMPASS[Math.floor(((d % 360) + 11.25) / 22.5) % 16] : "–");
  const num = (v, dp, unit) => (fin(v) ? v.toFixed(dp) + (unit ? " " + unit : "") : "–");
  const host = (sel) => document.querySelector(sel);
  const T = D.track;
  const phaseAt = (t) => { const p = D.phases.find((x) => x.kind === "leg" && t >= x.t0 && t < x.t1); return p ? p.name : ""; };
  const trackRows = (i) => [
    { name: "SOG", value: num(T.sog[i], 1, "kt"), color: BOAT },
    { name: "STW (corrected)", value: num(T.stw[i], 1, "kt"), color: BOAT, dash: true },
    { name: "Wind", value: `${num(T.tws[i], 0, "kt")} ${compass(T.twd[i])}` },
    { name: "TWA", value: fin(T.twa[i]) ? `${Math.round(Math.abs(T.twa[i]))}° ${T.twa[i] >= 0 ? "stbd" : "port"}` : "–" },
  ];

  // ------------------------------------------------------------ map
  const mp = host("#chart-map .chart-body");
  if (mp) {
    DA.legend(host("#chart-map .legend"), [
      { label: `${D.boat} (marker every hour)`, color: BOAT, marker: "circle" },
      ...D.routes.map((r) => ({ label: `${r.model} route`, color: style(r.model).color, dash: style(r.model).dash })),
      { label: "hole / the change", kind: "dot", marker: "diamond", color: "var(--ink-2)" },
    ]);
    const pts = [];
    for (const h of D.holes) {
      const k = DA.nearest(T.t, (h[0] + h[1]) / 2);
      pts.push({ lat: T.lat[k], lon: T.lon[k], shape: "diamond", color: "var(--ink)", label: `hole ${hm(h[0])}–${hm(h[1])}` });
    }
    if (D.change) {
      const k = DA.nearest(T.t, D.change.onset);
      pts.push({ lat: T.lat[k], lon: T.lon[k], shape: "diamond", color: "var(--ink)", label: `the change ${hm(D.change.onset)}` });
    }
    DA.mount(mp, () => DA.map(mp, {
      land: D.land, coast: D.coast, islands: D.islands, marks: D.marks, points: pts,
      aria: `${D.boat}'s track with the optimal routes and course marks`,
      routes: [
        ...D.routes.map((r) => Object.assign({ name: `${r.model} route`, t: r.t, lat: r.lat, lon: r.lon, width: 1.5, opacity: 0.85,
          hourly: false, info: (i) => [{ name: "Forecast", value: `${num(r.tws[i], 0, "kt")} ${compass(r.twd[i])}` }] }, style(r.model))),
        { name: D.boat, t: T.t, lat: T.lat, lon: T.lon, color: BOAT, width: 3, marker: "circle", info: trackRows },
      ],
    }));
  }

  // ------------------------------------------------------------ race timeline
  const tlh = host("#chart-timeline .chart-body");
  if (tlh) {
    DA.legend(host("#chart-timeline .legend"), [
      { label: "SOG", color: BOAT }, { label: "boat speed, corrected", color: BOAT, dash: "5 4" },
    ]);
    const ax = DA.dirAxis(T.twd);
    const dirT = [], dirV = [];
    for (let i = 0; i < T.t.length; i += 6) { dirT.push(T.t[i]); dirV.push(ax.wrap(T.twd[i])); }
    const vlines = D.passages.filter((p) => fin(p.t)).map((p) => ({ t: p.t, label: p.key ? `${p.label} ${hm(p.t)}` : null, strong: p.key }));
    if (D.change) vlines.push({ t: D.change.onset, label: `the change ${hm(D.change.onset)}`, strong: true });
    DA.mount(tlh, () => DA.timePanels(tlh, {
      t0: D.start - 300, t1: D.finish + 300, snap: T.t, vlines,
      bands: D.holes.map((h) => ({ t0: h[0], t1: h[1], label: "hole" })),
      strip: { segments: D.phases.filter((p) => p.kind === "leg").map((p) => ({ t0: p.t0, t1: p.t1, text: p.short, kind: "jib" })) },
      aria: `${D.boat}'s speed and wind through the race`,
      panels: [
        { label: "Speed, kt", height: 104, zero: true, series: [
          { kind: "line", name: "SOG", t: T.t, y: T.sog, color: BOAT },
          { kind: "line", name: "STW", t: T.t, y: T.stw, color: BOAT, dash: "5 4", width: 1.5 }] },
        { label: "True wind speed, kt (our instruments)", height: 96, zero: true, series: [
          { kind: "line", name: "TWS", t: T.t, y: T.tws, color: BOAT }] },
        { label: "True wind direction, ° true", height: 72, domain: ax.domain, ticks: ax.ticks, fmt: ax.fmt,
          series: [{ kind: "dots", name: "TWD", t: dirT, y: dirV, color: BOAT, dense: true }] },
      ],
      tip: (t) => { const i = DA.nearest(T.t, t); return { head: `${hm(T.t[i])} · ${phaseAt(T.t[i])}`, rows: trackRows(i) }; },
    }));
  }

  // ------------------------------------------------------------ splits: minutes behind (+) / ahead (−) of each route
  const sp = host("#chart-splits .chart-body");
  if (sp && D.splits.marks.length) {
    const S = D.splits;
    DA.legend(host("#chart-splits .legend"), S.models.map((m) => ({ label: `vs ${m} route`, color: style(m).color, dash: style(m).dash, marker: style(m).marker })));
    const xs = S.marks.map((k) => k.x);
    const turn = S.marks.find((k) => k.turning);
    DA.mount(sp, () => DA.xyLines(sp, {
      x0: 0, x1: S.length, height: 300, zero: true, endLabels: true,
      endFmt: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)} min`,
      yLabel: "minutes behind (+) or ahead (−) of the route", xLabel: "distance along the course, nm",
      xTicks: [{ x: 0, label: "Start" }, ...[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 150, 200, 250].filter((v) => v < S.length - 4).map((v) => ({ x: v, label: String(v) })), { x: S.length, label: "Finish" }],
      vlines: turn ? [{ x: turn.x, label: turn.label }] : [],
      series: S.models.map((m) => ({ name: m, x: xs, y: S.delta[m], color: style(m).color, dash: style(m).dash, marker: style(m).marker })),
      snap: xs, aria: "Minutes behind or ahead of each optimal route at every mark",
      tip: (k) => ({ head: `${S.marks[k].label} · ${hm(S.marks[k].t)}`, rows: S.models.map((m) => ({
        name: `vs ${m} (route ${fin(S.route[m][k]) ? hm(S.route[m][k]) : "–"})`, color: style(m).color,
        value: fin(S.delta[m][k]) ? `${S.delta[m][k] > 0 ? "+" : S.delta[m][k] < 0 ? "−" : ""}${Math.abs(S.delta[m][k])} min` : "–" })) }),
    }));
  }

  // ------------------------------------------------------------ forecast along each route vs what we measured
  const fo = host("#chart-forecast .chart-body");
  if (fo && D.forecasts.length) {
    DA.legend(host("#chart-forecast .legend"), [
      { label: "measured (10-min mean, over the ground)", color: BOAT },
      ...D.forecasts.map((f) => ({ label: `${f.model} along its route`, color: style(f.model).color, dash: style(f.model).dash, marker: style(f.model).marker })),
    ]);
    const W10 = D.wind10;
    const ax = DA.dirAxis(W10.twd, ...D.forecasts.map((f) => f.twd));
    const vl = [];
    const turn = D.passages.find((p) => p.key && p.turning);
    if (turn) vl.push({ t: turn.t, label: `${turn.label} ${hm(turn.t)}`, strong: true });
    if (D.change) vl.push({ t: D.change.onset, label: `the change ${hm(D.change.onset)}`, strong: true });
    DA.mount(fo, () => DA.timePanels(fo, {
      t0: D.start - 300, t1: D.finish + 300, vlines: vl, endLabels: true,
      snap: W10.t, aria: "Forecast wind along each route against the wind we measured",
      panels: [
        { label: "True wind speed, kt", height: 120, zero: true, series: [
          ...D.forecasts.map((f) => ({ kind: "line", name: f.model, t: f.t, y: f.tws, color: style(f.model).color, dash: style(f.model).dash })),
          { kind: "line", name: "measured", t: W10.t, y: W10.tws, color: BOAT, width: 3 }] },
        { label: "True wind direction, ° true", height: 96, domain: ax.domain, ticks: ax.ticks, fmt: ax.fmt, series: [
          ...D.forecasts.map((f) => ({ kind: "dots", name: f.model, t: f.t, y: f.twd.map(ax.wrap), color: style(f.model).color, marker: style(f.model).marker })),
          { kind: "dots", name: "measured", t: W10.t, y: W10.twd.map(ax.wrap), color: BOAT }] },
      ],
      tip: (t) => {
        const i = DA.nearest(W10.t, t);
        const rows = [{ name: "measured", value: `${num(W10.tws[i], 0, "kt")} ${compass(W10.twd[i])}`, color: BOAT }];
        for (const f of D.forecasts) {
          if (!f.t.length || t < f.t[0] - 1800 || t > f.t[f.t.length - 1] + 1800) continue;
          const k = DA.nearest(f.t, t);
          rows.push({ name: `${f.model} (${hm(f.t[k])})`, value: `${num(f.tws[k], 0, "kt")} ${compass(f.twd[k])}`, color: style(f.model).color });
        }
        return { head: hm(W10.t[i]), rows };
      },
    }));
  }
})();
