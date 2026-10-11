"use strict";
/* Day Before page: builds the chart specs from the embedded briefing data (see report/day_before.py). */
(function () {
  const D = JSON.parse(document.getElementById("da-data").textContent);
  DA.setZone(D.tz);
  const fin = DA.fin, hm = DA.hm;
  const STYLE = {
    GFS: { color: "var(--m-gfs)", dash: "6 3", marker: "circle" },
    ECMWF: { color: "var(--m-ecmwf)", dash: "2 2", marker: "square" },
    ACCESS: { color: "var(--m-access)", dash: "8 3 2 3", marker: "triangle" },
  };
  const style = (m) => STYLE[m] || { color: "var(--m-other)", dash: null, marker: "diamond" };
  const COMPASS = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split(" ");
  const compass = (d) => (fin(d) ? COMPASS[Math.floor(((d % 360) + 11.25) / 22.5) % 16] : "–");
  const num = (v, dp, unit) => (fin(v) ? v.toFixed(dp) + (unit ? " " + unit : "") : "–");
  const isKite = (s) => /^(A\d|S\d|kite|spin|code)/i.test(s);
  const nearest = (ts, t) => { let b = 0; for (let i = 1; i < ts.length; i++) if (Math.abs(ts[i] - t) < Math.abs(ts[b] - t)) b = i; return b; };
  const host = (sel) => document.querySelector(sel);

  // theme button: auto -> light -> dark
  const btn = host(".theme-btn");
  const store = { get() { try { return localStorage.getItem("da-theme"); } catch (e) { return null; } },
                  set(v) { try { v ? localStorage.setItem("da-theme", v) : localStorage.removeItem("da-theme"); } catch (e) { /* private mode */ } } };
  function applyTheme(v) {
    if (v) document.documentElement.setAttribute("data-theme", v); else document.documentElement.removeAttribute("data-theme");
    if (btn) btn.textContent = v === "dark" ? "Theme: dark" : v === "light" ? "Theme: light" : "Theme: auto";
  }
  applyTheme(store.get());
  if (btn) btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur === null ? "light" : cur === "light" ? "dark" : null;
    store.set(next); applyTheme(next);
  });

  const models = D.models;
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
      rows: models.map((m) => {
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
      }),
    }));
  }

  // ------------------------------------------------------------ meteograms (Expedition colours)
  for (const m of models) {
    const root = host(`#met-${m.model} .chart-body`);
    if (!root) continue;
    const panels = [{
      label: "Wind speed, kt (dashed: gusts)", height: 104, zero: true,
      series: [
        { kind: "band", t: m.t, y: m.tws, y2: m.twg, color: "var(--met-tws)" },
        { kind: "line", name: "Wind", t: m.t, y: m.tws, color: "var(--met-tws)" },
        { kind: "line", name: "Gust", t: m.t, y: m.twg, color: "var(--met-tws)", dash: "5 4", width: 1.5 },
      ],
    }, {
      label: "Wind direction, ° true", height: 72, domain: [0, 360], ticks: [0, 90, 180, 270, 360],
      fmt: (v) => ({ 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" })[v],
      series: [{ kind: "dots", name: "Direction", t: m.t, y: m.twd, color: "var(--met-tws)" }],
    }, {
      label: "Pressure, hPa", height: 84, minSpan: 4,
      series: [{ kind: "line", name: "Pressure", t: m.t, y: m.mslp, color: "var(--met-pressure)" }],
    }];
    if (m.airt) panels.push({ label: "Air temperature, °C", height: 72, minSpan: 3,
      series: [{ kind: "line", name: "Air", t: m.t, y: m.airt, color: "var(--met-temp)" }] });
    if (m.rain && m.rain.some((v) => fin(v) && v > 0)) panels.push({ label: "Rain, mm/h", height: 64, zero: true,
      series: [{ kind: "bars", name: "Rain", t: m.t, y: m.rain, color: "var(--met-rain)" }] });
    const vlines = m.marks.map((k) => ({ t: k.t, label: k.turning ? `${k.name} ${hm(k.t)}` : null, strong: k.turning }));
    const bands = m.change ? [{ t0: m.change.t_from, t1: m.change.t_to, label: "change" }] : [];
    DA.mount(root, () => DA.timePanels(root, {
      t0: m.t[0], t1: m.t[m.t.length - 1], panels, vlines, bands, snap: m.t,
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
        return { head: `${m.model} · ${hm(m.t[i])}${m.mark[i] ? " · " + m.mark[i] : ""}`, rows };
      },
    }));
  }

  // ------------------------------------------------------------ models side by side
  const cmp = host("#chart-compare .chart-body");
  if (cmp) {
    DA.legend(host("#chart-compare .legend"), models.map((m) => ({ label: m.model, color: style(m.model).color, dash: style(m.model).dash, marker: style(m.model).marker })));
    const snap = [...new Set(models.flatMap((m) => m.t))].sort((a, b) => a - b);
    DA.mount(cmp, () => DA.timePanels(cmp, {
      t0: tMin, t1: tMax, snap, endLabels: true, aria: "Wind speed, direction and pressure along each model's route",
      vlines: [{ t: D.gun, label: "gun" }],
      panels: [
        { label: "Wind speed, kt", height: 110, zero: true,
          series: models.map((m) => ({ kind: "line", name: m.model, t: m.t, y: m.tws, color: style(m.model).color, dash: style(m.model).dash })) },
        { label: "Wind direction, ° true", height: 84, domain: [0, 360], ticks: [0, 90, 180, 270, 360],
          fmt: (v) => ({ 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" })[v],
          series: models.map((m) => ({ kind: "dots", name: m.model, t: m.t, y: m.twd, color: style(m.model).color, marker: style(m.model).marker })) },
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
      rows: models.map((m) => ({
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
      })),
    }));
  }

  // ------------------------------------------------------------ map
  const mp = host("#chart-map .chart-body");
  if (mp) {
    DA.legend(host("#chart-map .legend"), [
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
        ] }, style(m.model))),
      points: models.filter((m) => m.change && fin(m.change.lat)).map((m) => ({ lat: m.change.lat, lon: m.change.lon, shape: "diamond", color: style(m.model).color, label: `${m.model} change ${hm(m.change.t)}` })),
    }));
  }
})();
