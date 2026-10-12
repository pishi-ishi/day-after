"use strict";
/* Navigator edition (Day After): charts from the embedded race data (see report/navigator.py).
   Our boat is always blue (--boat); each model keeps its fixed colour, dash and marker. */
(function () {
  const D = JSON.parse(document.getElementById("da-data").textContent);
  DA.setZone(D.tz);
  DA.themeButton(document.querySelector(".theme-btn"));
  const fin = DA.fin, hm = DA.hm;
  const style = DA.modelStyle;
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
  // ------------------------------------------------------------ GRIB models at our position vs what we measured
  const gr = host("#chart-grib .chart-body");
  if (gr && D.grib) {
    const G = D.grib;
    DA.legend(host("#chart-grib .legend"), [
      { label: "measured (10-min mean, over the ground)", color: BOAT },
      ...G.models.map((m) => ({ label: `${m.model} at our position`, color: style(m.model).color, dash: style(m.model).dash, marker: style(m.model).marker })),
    ]);
    const ax = DA.dirAxis(G.obs.twd, ...G.models.map((m) => m.twd));
    const vl = [];
    const turn = D.passages.find((p) => p.key && p.turning);
    if (turn) vl.push({ t: turn.t, label: `${turn.label} ${hm(turn.t)}`, strong: true });
    if (D.change) vl.push({ t: D.change.onset, label: `the change ${hm(D.change.onset)}`, strong: true });
    DA.mount(gr, () => DA.timePanels(gr, {
      t0: D.start - 300, t1: D.finish + 300, vlines: vl, endLabels: true, snap: G.obs.t,
      aria: "Each GRIB model's wind at our position against the wind we measured",
      panels: [
        { label: "True wind speed, kt", height: 130, zero: true, series: [
          ...G.models.map((m) => ({ kind: "line", name: m.model, t: m.t, y: m.tws, color: style(m.model).color, dash: style(m.model).dash })),
          { kind: "line", name: "measured", t: G.obs.t, y: G.obs.tws, color: BOAT, width: 3 }] },
        { label: "True wind direction, ° true", height: 96, domain: ax.domain, ticks: ax.ticks, fmt: ax.fmt, series: [
          ...G.models.map((m) => ({ kind: "dots", name: m.model, t: m.t, y: m.twd.map(ax.wrap), color: style(m.model).color, marker: style(m.model).marker })),
          { kind: "dots", name: "measured", t: G.obs.t, y: G.obs.twd.map(ax.wrap), color: BOAT }] },
      ],
      tip: (t) => {
        const i = DA.nearest(G.obs.t, t);
        return { head: `${hm(G.obs.t[i])} · ${phaseAt(G.obs.t[i])}`, rows: [
          { name: "measured", value: `${num(G.obs.tws[i], 0, "kt")} ${compass(G.obs.twd[i])}`, color: BOAT },
          ...G.models.map((m) => ({ name: m.model, value: `${num(m.tws[i], 0, "kt")} ${compass(m.twd[i])}${fin(m.gust[i]) ? " · gust " + num(m.gust[i], 0) : ""}`, color: style(m.model).color })),
        ] };
      },
    }));
  }

  // ------------------------------------------------------------ performance: polar %, targets, manoeuvres
  const PF = D.perf;
  if (PF) {
    const SIDES = [
      { pos: "upwind", label: "upwind", dash: null, marker: "circle" },
      { pos: "reach", label: "reach", dash: "6 3", marker: "square" },
      { pos: "downwind", label: "downwind", dash: "2 2", marker: "triangle" },
    ];
    const pp = host("#chart-polarpct .chart-body");
    if (pp && PF.buckets.length) {
      DA.legend(host("#chart-polarpct .legend"), SIDES.map((s) => ({ label: s.label, color: BOAT, dash: s.dash, marker: s.marker })));
      const mids = [...new Set(PF.buckets.map((b) => b.tws0 + 1))].sort((a, b) => a - b);
      const ser = SIDES.map((s) => {
        const bs = PF.buckets.filter((b) => b.pos === s.pos);
        return { name: s.label, x: bs.map((b) => b.tws0 + 1), y: bs.map((b) => Math.round(b.pct)), color: BOAT, dash: s.dash, marker: s.marker };
      }).filter((s) => s.x.length);
      DA.mount(pp, () => DA.xyLines(pp, {
        x0: Math.max(0, mids[0] - 1), x1: mids[mids.length - 1] + 1, height: 260, y0: 80, y1: 105, ref: 100, endLabels: true,
        endFmt: (v) => `${v} %`, yLabel: "% of polar speed (median)", xLabel: "true wind speed, kt",
        vlines: PF.tws_max < mids[mids.length - 1] ? [{ x: PF.tws_max, label: `polar ends ${PF.tws_max} kt` }] : [],
        series: ser, snap: mids, aria: "Polar percentage by wind speed and point of sail",
        tip: (k) => ({ head: `${mids[k] - 1}–${mids[k] + 1} kt${mids[k] > PF.tws_max ? " (indicative)" : ""}`, rows: SIDES.map((s) => {
          const b = PF.buckets.find((x) => x.pos === s.pos && x.tws0 + 1 === mids[k]);
          return { name: s.label, color: BOAT, value: b ? `${Math.round(b.pct)} % · ${Math.round(b.n / 60)} min` : "–" };
        }) }),
      }));
    }
    const tg = host("#chart-targets .chart-body");
    if (tg && PF.targets.length) {
      DA.legend(host("#chart-targets .legend"), [{ label: "ours (best 75–95 % of VMG)", color: BOAT, marker: "circle" },
        { label: "polar target", color: "var(--muted)", dash: "5 4", marker: "diamond" }]);
      const mids = [...new Set(PF.targets.map((x) => x.tws0 + 1))].sort((a, b) => a - b);
      const ser = [];
      for (const side of ["upwind", "downwind"]) {
        const xs = PF.targets.filter((x) => x.side === side);
        if (!xs.length) continue;
        ser.push({ name: `polar ${side}`, x: xs.map((x) => x.tws0 + 1), y: xs.map((x) => Math.round(x.polar_twa)), color: "var(--muted)", dash: "5 4", marker: "diamond" });
        ser.push({ name: `ours ${side}`, x: xs.map((x) => x.tws0 + 1), y: xs.map((x) => Math.round(x.twa)), color: BOAT, marker: "circle" });
      }
      DA.mount(tg, () => DA.xyLines(tg, {
        x0: Math.max(0, mids[0] - 1), x1: mids[mids.length - 1] + 1, height: 280, y0: 30, y1: 180, yLabel: "true wind angle, °",
        xLabel: "true wind speed, kt", series: ser, snap: mids, aria: "Target wind angles, ours against the polar",
        vlines: PF.tws_max < mids[mids.length - 1] ? [{ x: PF.tws_max, label: `polar ends ${PF.tws_max} kt` }] : [],
        tip: (k) => ({ head: `${mids[k] - 1}–${mids[k] + 1} kt`, rows: PF.targets.filter((x) => x.tws0 + 1 === mids[k]).flatMap((x) => [
          { name: `${x.side}: ours`, color: BOAT, value: `${Math.round(x.twa)}° · ${x.stw.toFixed(1)} kt · VMG ${x.vmg.toFixed(1)}` },
          { name: `${x.side}: polar`, color: "var(--muted)", value: `${Math.round(x.polar_twa)}° · ${x.polar_stw.toFixed(1)} kt · VMG ${x.polar_vmg.toFixed(1)}` }]) }),
      }));
    }
    const mn = host("#chart-manoeuvres .chart-body");
    if (mn && PF.manoeuvres.length) {
      DA.legend(host("#chart-manoeuvres .legend"), [{ label: "tack", kind: "dot", marker: "circle", color: BOAT },
        { label: "gybe", kind: "dot", marker: "diamond", color: BOAT }]);
      const ws = PF.manoeuvres.map((m) => m.tws);
      const x0 = Math.floor(Math.min(...ws) / 5) * 5, x1 = Math.ceil(Math.max(...ws) / 5) * 5;
      const ticks = [];
      for (let v = x0; v <= x1; v += 5) ticks.push({ x: v, label: String(v) });
      const worst = PF.manoeuvres.slice(0, 3);
      DA.mount(mn, () => DA.scatter(mn, {
        x0, x1, xTicks: ticks, height: 260, yLabel: "loss, m (along the wind)", xLabel: "true wind speed, kt",
        aria: "Loss in metres per tack and gybe against the wind speed",
        points: PF.manoeuvres.map((m) => ({ x: m.tws, y: m.loss_m, color: BOAT, shape: m.kind === "tack" ? "circle" : "diamond", r: 5,
          label: worst.includes(m) ? `${m.kind} ${hm(m.t)}` : null, head: `${m.kind} ${hm(m.t)}`,
          tip: [{ name: "loss", value: `${Math.round(m.loss_m)} m · ${Math.round(m.loss_s)} s` },
            { name: "speed", value: `${m.stw_before.toFixed(1)} → ${m.stw_min.toFixed(1)} kt` },
            { name: "wind", value: `${Math.round(m.tws)} kt` }] })),
      }));
    }
  }

  // ------------------------------------------------------------ fleet
  const FL = D.fleet;
  if (FL) {
    const gp = host("#chart-gaps .chart-body");
    if (gp) {
      DA.legend(host("#chart-gaps .legend"), [{ label: D.boat, color: BOAT }, ...FL.rivals.map((r) => ({ label: r.name, color: r.color, marker: "circle" }))]);
      DA.mount(gp, () => DA.xyLines(gp, {
        x0: 0, x1: FL.course, height: 300, zero: true, endLabels: true,
        endFmt: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`,
        yLabel: "corrected minutes: behind us (+) or ahead of us (−)", xLabel: "distance along the course, nm",
        xTicks: [{ x: 0, label: "Start" }, ...[10, 20, 30, 40, 50, 60, 70, 80, 100, 150, 200, 250].filter((v) => v < FL.course - 4).map((v) => ({ x: v, label: String(v) })), { x: FL.course, label: "Finish" }],
        vlines: FL.turning ? [{ x: FL.turning, label: "turning mark" }] : [],
        series: [{ name: D.boat, x: FL.gates, y: FL.gates.map(() => 0), color: BOAT, marker: "circle" },
          ...FL.rivals.map((r) => ({ name: r.name, x: FL.gates, y: r.gaps, color: r.color, marker: "circle" }))],
        snap: FL.gates, aria: "Corrected-time gap to each rival along the course",
        tip: (k) => ({ head: `${FL.gates[k].toFixed(1)} nm (${FL.labels[k]}) · our corrected rank ${FL.ranks[k] > 0 ? FL.ranks[k] : "–"}`,
          rows: FL.rivals.map((r) => ({ name: r.name, color: r.color, value: fin(r.gaps[k]) ? `${r.gaps[k] > 0 ? "+" : ""}${r.gaps[k].toFixed(1)} min` : "–" })) }),
      }));
    }
    const rd = host("#chart-rounding .chart-body");
    if (rd && FL.scatter.length) {
      DA.legend(host("#chart-rounding .legend"), [{ label: D.boat, kind: "dot", color: BOAT },
        ...FL.rivals.map((r) => ({ label: r.name, kind: "dot", color: r.color })), { label: "rest of the fleet", kind: "dot", color: "var(--fleet)" }]);
      const xs = FL.scatter.map((p) => p.x);
      const x0 = Math.min(...xs) - 600, x1 = Math.max(...xs) + 600;
      const ticks = [];
      for (let t = Math.ceil(x0 / 1800) * 1800; t <= x1; t += 1800) ticks.push({ x: t, label: hm(t) });
      const colour = (p) => p.kind === "us" ? BOAT : p.kind === "rival" ? (FL.rivals.find((r) => r.name === p.name) || {}).color : "var(--fleet)";
      const order = { other: 0, rival: 1, us: 2 };
      DA.mount(rd, () => DA.scatter(rd, {
        x0, x1, xTicks: ticks, height: 300, yLabel: "corrected time from the rounding to the finish, h", xLabel: "time of rounding",
        aria: "Rounding time against corrected time home for every finisher",
        points: FL.scatter.slice().sort((a, b) => order[a.kind] - order[b.kind]).map((p) => ({
          x: p.x, y: p.y, color: colour(p), r: p.kind === "other" ? 4 : 5,
          label: p.kind !== "other" || p.place <= 3 ? `${p.name}${p.place ? " (" + p.place + ")" : ""}` : null,
          head: `${p.name}${p.place ? " · " + p.place : ""}`,
          tip: [{ name: "rounded", value: hm(p.x) }, { name: "home, corrected", value: `${p.y.toFixed(2)} h` }] })),
      }));
    }
    const fm = host("#chart-fleetmap .chart-body");
    if (fm) {
      DA.legend(host("#chart-fleetmap .legend"), [{ label: D.boat, color: BOAT }, ...FL.rivals.map((r) => ({ label: r.name, color: r.color, marker: "circle" }))]);
      DA.mount(fm, () => DA.map(fm, {
        land: D.land, coast: D.coast, islands: D.islands, marks: D.marks, aria: "Our track and the rivals' tracks",
        routes: [...FL.rivals.map((r) => ({ name: r.name, t: r.track.t, lat: r.track.lat, lon: r.track.lon, color: r.color, width: 1.8, marker: "circle",
          info: () => [] })), { name: D.boat, t: T.t, lat: T.lat, lon: T.lon, color: BOAT, width: 2.5, marker: "circle", info: trackRows }],
      }));
    }
  }
})();
