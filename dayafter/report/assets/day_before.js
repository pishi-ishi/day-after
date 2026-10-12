"use strict";
/* Day Before page: builds the chart specs from the embedded briefing data (see report/day_before.py). */
(function () {
  const D = JSON.parse(document.getElementById("da-data").textContent);
  DA.setZone(D.tz);
  const fin = DA.fin, hm = DA.hm;
  const style = DA.modelStyle;
  const COMPASS = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split(" ");
  const compass = (d) => (fin(d) ? COMPASS[Math.floor(((d % 360) + 11.25) / 22.5) % 16] : "–");
  const num = (v, dp, unit) => (fin(v) ? v.toFixed(dp) + (unit ? " " + unit : "") : "–");
  const isKite = (s) => /^(A\d|S\d|kite|spin|code)/i.test(s);
  const nearest = (ts, t) => { let b = 0; for (let i = 1; i < ts.length; i++) if (Math.abs(ts[i] - t) < Math.abs(ts[b] - t)) b = i; return b; };
  const host = (sel) => document.querySelector(sel);

  DA.themeButton(document.querySelector(".theme-btn"));

  const models = D.models;
  const A = D.after;  // crew edition: what we measured, our rounding, the change, the sails we flew
  const BOAT = "var(--boat)";
  const tMin = Math.min(D.gun, ...models.map((m) => m.t[0]));
  const tMax = Math.max(...models.map((m) => m.t[m.t.length - 1]));

  // ------------------------------------------------------------ change window
  const win = host("#chart-window .chart-body");
  if (win) {
    DA.legend(host("#chart-window .legend"), [
      { label: "the change (largest sustained wind shift)", kind: "dot", marker: "diamond", color: "var(--ink-2)" },
      { label: `at ${D.turning || "the turning mark"}`, kind: "dot", marker: "circle", color: "var(--ink-2)" },
      { label: "window between the models", kind: "rect", color: "var(--band)" },
    ]);
    DA.mount(win, () => DA.timeRows(win, {
      t0: tMin, t1: tMax, aria: "When each model brings the wind change, against our time at the turning mark",
      bands: D.window ? [{ t0: D.window.t0, t1: Math.max(D.window.t1, D.window.t0 + 300), label: "change window" }] : [],
      vlines: [{ t: D.gun, label: "gun" }],
      rows: [...(A ? [{
        label: "Actual", key: { color: BOAT },
        marks: [...(A.change ? [{ t: A.change.t, shape: "diamond", color: BOAT, r: 6, label: hm(A.change.t) }] : []),
          ...(fin(A.turning_t) ? [{ t: A.turning_t, shape: "circle", color: BOAT, r: 5, label: hm(A.turning_t), below: true }] : [])],
        tip: () => [...(A.change ? [{ name: `the change (${compass(A.change.from)} → ${compass(A.change.to)})`, value: hm(A.change.t), color: BOAT }] : []),
          ...(fin(A.turning_t) ? [{ name: `we rounded ${D.turning}`, value: hm(A.turning_t), color: BOAT }] : [])],
      }] : []), ...models.map((m) => {
        const st = style(m.model);
        const marks = [];
        if (m.change) marks.push({ t: m.change.t, shape: "diamond", color: st.color, r: 6, label: hm(m.change.t) });
        if (fin(m.eta)) marks.push({ t: m.eta, shape: "circle", color: st.color, r: 5, label: hm(m.eta), below: true });
        return {
          label: m.model, key: st, marks,
          tip: (t) => {
            const out = [];
            if (m.change) out.push({ name: `${m.model} change (${compass(m.change.from)} → ${compass(m.change.to)})`, value: hm(m.change.t), color: st.color });
            if (fin(m.eta)) out.push({ name: `${m.model} at ${D.turning}`, value: hm(m.eta), color: st.color });
            return out;
          },
        };
      })],
    }));
  }

  // ------------------------------------------------------------ meteograms (Expedition colours)
  for (const m of models) {
    const root = host(`#met-${m.model} .chart-body`);
    if (!root) continue;
    const axm = A ? DA.dirAxis(m.twd, A.obs.twd) : DA.dirAxis(m.twd);
    const panels = [{
      label: "Wind speed, kt (dashed: gusts)", height: 104, zero: true,
      series: [
        { kind: "band", t: m.t, y: m.tws, y2: m.twg, color: "var(--met-tws)" },
        { kind: "line", name: "Wind", t: m.t, y: m.tws, color: "var(--met-tws)" },
        { kind: "line", name: "Gust", t: m.t, y: m.twg, color: "var(--met-tws)", dash: "5 4", width: 1.5 },
        ...(A ? [{ kind: "line", name: "Measured", t: A.obs.t, y: A.obs.tws, color: BOAT, width: 3 }] : []),
      ],
    }, {
      label: "Wind direction, ° true", height: 72, domain: axm.domain, ticks: axm.ticks, fmt: axm.fmt,
      series: [{ kind: "dots", name: "Direction", t: m.t, y: m.twd.map(axm.wrap), color: "var(--met-tws)" },
        ...(A ? [{ kind: "dots", name: "Measured", t: A.obs.t, y: A.obs.twd.map(axm.wrap), color: BOAT }] : [])],
    }, {
      label: "Pressure, hPa", height: 84, minSpan: 4,
      series: [{ kind: "line", name: "Pressure", t: m.t, y: m.mslp, color: "var(--met-pressure)" }],
    }];
    if (m.airt) panels.push({ label: "Air temperature, °C", height: 72, minSpan: 3,
      series: [{ kind: "line", name: "Air", t: m.t, y: m.airt, color: "var(--met-temp)" }] });
    if (m.rain && m.rain.some((v) => fin(v) && v > 0)) panels.push({ label: "Rain, mm/h", height: 64, zero: true,
      series: [{ kind: "bars", name: "Rain", t: m.t, y: m.rain, color: "var(--met-rain)" }] });
    const vlines = m.marks.map((k) => ({ t: k.t, label: k.turning ? `${k.name} ${hm(k.t)}` : null, strong: k.turning }));
    if (A && fin(A.turning_t)) vlines.push({ t: A.turning_t, label: `we rounded ${hm(A.turning_t)}`, dash: true });
    const bands = m.change ? [{ t0: m.change.t_from, t1: m.change.t_to, label: "change" }] : [];
    DA.mount(root, () => DA.timePanels(root, {
      t0: Math.min(m.t[0], A ? A.start : Infinity), t1: Math.max(m.t[m.t.length - 1], A ? A.finish : -Infinity), panels, vlines, bands, snap: m.t,
      strip: { segments: m.sails.map((s) => ({ t0: s.t0, t1: s.t1, text: s.sail, kind: isKite(s.sail) ? "kite" : "jib" })) },
      aria: `${m.model} forecast along its optimal route: wind, direction, pressure${m.airt ? ", air temperature" : ""} and rain`,
      tip: (t) => {
        const i = nearest(m.t, t);
        const rows = [
          { name: "Wind", value: num(m.tws[i], 1, "kt"), color: "var(--met-tws)" },
          { name: "Gust", value: num(m.twg[i], 1, "kt"), color: "var(--met-tws)", dash: true },
          { name: "Direction", value: fin(m.twd[i]) ? `${Math.round(m.twd[i])}° ${compass(m.twd[i])}` : "–" },
          { name: "Pressure", value: num(m.mslp[i], 1, "hPa"), color: "var(--met-pressure)" },
        ];
        if (m.airt) rows.push({ name: "Air", value: num(m.airt[i], 1, "°C"), color: "var(--met-temp)" });
        if (m.rain) rows.push({ name: "Rain", value: num(m.rain[i], 2, "mm/h"), color: "var(--met-rain)" });
        if (fin(m.twa[i])) rows.push({ name: "TWA", value: `${Math.round(Math.abs(m.twa[i]))}° ${m.twa[i] >= 0 ? "stbd" : "port"}` });
        if (m.sail[i]) rows.push({ name: "Sail", value: m.sail[i] });
        if (A) {
          const k = DA.nearest(A.obs.t, t);
          if (Math.abs(A.obs.t[k] - t) <= 600) rows.push({ name: `Measured (${hm(A.obs.t[k])})`, value: `${num(A.obs.tws[k], 0, "kt")} ${compass(A.obs.twd[k])}`, color: BOAT });
        }
        return { head: `${m.model} · ${hm(m.t[i])}${m.mark[i] ? " · " + m.mark[i] : ""}`, rows };
      },
    }));
  }

  // ------------------------------------------------------------ models side by side
  const cmp = host("#chart-compare .chart-body");
  if (cmp) {
    DA.legend(host("#chart-compare .legend"), models.map((m) => ({ label: m.model, color: style(m.model).color, dash: style(m.model).dash, marker: style(m.model).marker })));
    const snap = [...new Set(models.flatMap((m) => m.t))].sort((a, b) => a - b);
    const axc = DA.dirAxis(...models.map((m) => m.twd));
    DA.mount(cmp, () => DA.timePanels(cmp, {
      t0: tMin, t1: tMax, snap, endLabels: true, aria: "Wind speed, direction and pressure along each model's route",
      vlines: [{ t: D.gun, label: "gun" }],
      panels: [
        { label: "Wind speed, kt", height: 110, zero: true,
          series: models.map((m) => ({ kind: "line", name: m.model, t: m.t, y: m.tws, color: style(m.model).color, dash: style(m.model).dash })) },
        { label: "Wind direction, ° true", height: 84, domain: axc.domain, ticks: axc.ticks, fmt: axc.fmt,
          series: models.map((m) => ({ kind: "dots", name: m.model, t: m.t, y: m.twd.map(axc.wrap), color: style(m.model).color, marker: style(m.model).marker })) },
        { label: "Pressure, hPa", height: 84, minSpan: 4,
          series: models.map((m) => ({ kind: "line", name: m.model, t: m.t, y: m.mslp, color: style(m.model).color, dash: style(m.model).dash })) },
      ],
      tip: (t) => ({ head: hm(t), rows: models.flatMap((m) => {
        if (t < m.t[0] - 1800 || t > m.t[m.t.length - 1] + 1800) return [];
        const i = nearest(m.t, t);
        return [{ name: `${m.model} (${hm(m.t[i])})`, value: `${num(m.tws[i], 0, "kt")} ${compass(m.twd[i])} · ${num(m.mslp[i], 0, "hPa")}`, color: style(m.model).color }];
      }) }),
    }));
  }

  // ------------------------------------------------------------ sails, tacks and gybes
  const sl = host("#chart-sails .chart-body");
  if (sl) {
    DA.legend(host("#chart-sails .legend"), [
      { label: "headsail", kind: "rect", color: "var(--sail-jib)" },
      { label: "kite (A-sail)", kind: "rect", color: "var(--sail-kite)" },
      { label: "tack or gybe", kind: "dot", marker: "diamond", color: "var(--ink)" },
    ]);
    DA.mount(sl, () => DA.timeRows(sl, {
      t0: tMin, t1: tMax, rowH: 46, aria: "Planned sails, tacks and gybes along each model's route",
      vlines: [{ t: D.gun, label: "gun" }],
      rows: [...(A && A.sails.length ? [{
        label: "We flew", key: { color: BOAT },
        segments: A.sails.map((s) => ({ t0: s.t0, t1: s.t1, text: s.sail, kind: isKite(s.sail) ? "kite" : "jib" })),
        marks: [],
        tip: (t) => { const s = A.sails.find((x) => t >= x.t0 && t < x.t1); return s ? [{ name: "we flew", value: s.sail, color: BOAT }] : []; },
      }] : []), ...models.map((m) => ({
        label: m.model, key: style(m.model),
        segments: m.sails.map((s) => ({ t0: s.t0, t1: s.t1, text: s.sail, kind: isKite(s.sail) ? "kite" : "jib" })),
        marks: m.manoeuvres.map((v) => ({ t: v.t, shape: "diamond", color: "var(--ink)", r: 3.5, top: true })),
        tip: (t) => {
          const s = m.sails.find((x) => t >= x.t0 && t < x.t1);
          const out = s ? [{ name: `${m.model} sail`, value: s.sail, color: style(m.model).color }] : [];
          const v = m.manoeuvres.find((x) => Math.abs(x.t - t) < 600);
          if (v) out.push({ name: `${m.model} ${v.kind}${v.mark ? " at " + v.mark : ""}`, value: hm(v.t) });
          return out;
        },
      }))],
    }));
  }

  // ------------------------------------------------------------ every GRIB model along one route
  const gg = host("#chart-gribs .chart-body");
  if (gg && D.gribs) {
    const G = D.gribs;
    DA.legend(host("#chart-gribs .legend"), [
      ...G.models.map((m) => ({ label: m.model, color: style(m.model).color, dash: style(m.model).dash, marker: style(m.model).marker })),
      ...(A ? [{ label: "measured", color: BOAT }] : []),
    ]);
    const ax = DA.dirAxis(...G.models.map((m) => m.twd), ...(A ? [A.obs.twd] : []));
    const t0 = G.models[0].t[0], t1 = G.models[0].t[G.models[0].t.length - 1];
    DA.mount(gg, () => DA.timePanels(gg, {
      t0, t1, snap: G.models[0].t, endLabels: true, aria: `Wind along the ${G.route_model} route in each GRIB model`,
      vlines: [{ t: D.gun, label: "gun" }],
      panels: [
        { label: "Wind speed, kt", height: 110, zero: true, series: [
          ...G.models.map((m) => ({ kind: "line", name: m.model, t: m.t, y: m.tws, color: style(m.model).color, dash: style(m.model).dash })),
          ...(A ? [{ kind: "line", name: "measured", t: A.obs.t, y: A.obs.tws, color: BOAT, width: 3 }] : [])] },
        { label: "Wind direction, ° true", height: 84, domain: ax.domain, ticks: ax.ticks, fmt: ax.fmt, series: [
          ...G.models.map((m) => ({ kind: "dots", name: m.model, t: m.t, y: m.twd.map(ax.wrap), color: style(m.model).color, marker: style(m.model).marker })),
          ...(A ? [{ kind: "dots", name: "measured", t: A.obs.t, y: A.obs.twd.map(ax.wrap), color: BOAT }] : [])] },
      ],
      tip: (t) => {
        const i = DA.nearest(G.models[0].t, t);
        const rows = G.models.map((m) => ({ name: m.model, value: `${num(m.tws[i], 0, "kt")} ${compass(m.twd[i])}${fin(m.gust[i]) ? " · gust " + num(m.gust[i], 0) : ""}`, color: style(m.model).color }));
        if (A) { const k = DA.nearest(A.obs.t, t); if (Math.abs(A.obs.t[k] - t) <= 600) rows.push({ name: "measured", value: `${num(A.obs.tws[k], 0, "kt")} ${compass(A.obs.twd[k])}`, color: BOAT }); }
        return { head: hm(G.models[0].t[i]), rows };
      },
    }));
  }

  // ------------------------------------------------------------ map
  const mp = host("#chart-map .chart-body");
  if (mp) {
    DA.legend(host("#chart-map .legend"), [
      ...(A ? [{ label: `${A.boat} (our track)`, color: BOAT, marker: "circle" }] : []),
      ...models.map((m) => ({ label: `${m.model} route (marker every hour)`, color: style(m.model).color, dash: style(m.model).dash, marker: style(m.model).marker })),
      { label: "the change on that route", kind: "dot", marker: "diamond", color: "var(--ink-2)" },
    ]);
    DA.mount(mp, () => DA.map(mp, {
      land: D.land, coast: D.coast, islands: D.islands, marks: D.course,
      aria: `Optimal routes for ${models.map((m) => m.model).join(", ")} on the course`,
      routes: models.map((m) => Object.assign({ name: m.model, t: m.t, lat: m.lat, lon: m.lon,
        info: (i) => [
          { name: "Wind", value: `${num(m.tws[i], 0, "kt")} ${compass(m.twd[i])}` },
          { name: "Pressure", value: num(m.mslp[i], 1, "hPa") },
          ...(m.sail[i] ? [{ name: "Sail", value: m.sail[i] }] : []),
          ...(m.mark[i] ? [{ name: "Mark", value: m.mark[i] }] : []),
        ] }, style(m.model))).concat(A ? [{ name: A.boat, t: A.track.t, lat: A.track.lat, lon: A.track.lon, color: BOAT, width: 3,
          marker: "circle", info: (i) => { const k = DA.nearest(A.obs.t, A.track.t[i]); return [{ name: "Measured", value: `${num(A.obs.tws[k], 0, "kt")} ${compass(A.obs.twd[k])}` }]; } }] : []),
      points: models.filter((m) => m.change && fin(m.change.lat)).map((m) => ({ lat: m.change.lat, lon: m.change.lon, shape: "diamond", color: style(m.model).color, label: `${m.model} change ${hm(m.change.t)}` })),
    }));
  }
})();
