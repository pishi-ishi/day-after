"""Skipper/owner edition (3–4 printed pages) and the 7 Seas client edition (the skipper edition with a 7 Seas
cover, colours and contact, plus the navigator detail as an appendix). Both reuse the navigator's sections and
data, so every number is the same as in the navigator edition."""
from __future__ import annotations

from .. import resources
from ..analysis.recommendations import bottom_line, recommendations
from ..core import timeutil
from . import html as H

SEVEN_SEAS = {
    "name": "7Seas Marine Electronics",
    "address": "66B Prince St, Mosman NSW 2088",
    "web": "7seasmarine.me",
    "email": "info@7seasmarine.me",
}


def _logo() -> str:
    try:
        with open(resources.asset_path("7seas_logo.svg"), encoding="utf-8") as f:
            svg = f.read()
    except OSError:
        return ""
    return svg[svg.index("<svg"):]


def render_body(a, parts: dict, edition: str) -> str:
    recs = recommendations(a)
    rec_html = "".join(f'<li><strong>{H.esc(r.title)}.</strong> {H.esc(r.text)}</li>' for r in recs)
    bl = bottom_line(a)
    skipper = f"""
<section id="summary" class="wrap">
  <h2>Bottom line</h2>
  <p class="verdict">{H.esc(bl)}</p>
  <div class="kpis">{parts["tiles"]}</div>
  <h3 class="sub-h">Decisions for next time</h3>
  <ol class="recs">{rec_html}</ol>
</section>
<section id="story" class="wrap">
  <h2>What decided the race</h2>
  <div class="findings">{parts["findings_top" if edition == "skipper" else "findings"]}</div>
  {parts["notes"]}
  {H.figure("chart-map", "Our track (blue) with the optimal routes and the course.", parts["marks_table"], "Table view: mark passages")}
</section>
<section id="plan" class="wrap">
  <h2>Plan vs reality</h2>
{parts["plan_head"]}
  <h3 class="sub-h">How good were the forecasts?</h3>
  {parts["score_table"]}
</section>
{parts["fleet_compact"] if edition == "skipper" else parts["fleet"]}
"""
    if edition == "skipper":
        toc = "".join(f'<a href="#{i}">{t}</a>' for i, t in
                      [("summary", "Bottom line"), ("story", "The race"), ("plan", "Plan vs reality"), ("fleet", "Fleet")])
        return f"""
<header class="wrap cover">
  <div class="topbar"><div class="eyebrow">Day After · skipper edition</div>
  <button class="theme-btn" type="button">Theme: auto</button></div>
  <h1>{H.esc(a.race_name)}</h1>
  <p class="sub">{H.esc(parts["sub"])}</p>
</header>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main>
{skipper}
{parts["footer"]}
</main>"""

    # 7 Seas client edition
    s = SEVEN_SEAS
    date = timeutil.fmt_local(a.gun, a.tz, "%d %B %Y")
    toc = "".join(f'<a href="#{i}">{t}</a>' for i, t in
                  [("summary", "Bottom line"), ("story", "The race"), ("plan", "Plan vs reality"), ("fleet", "Fleet"),
                   ("appendix", "Navigator appendix")])
    appendix = (parts["phases"] + parts["performance"] + parts["calibration"]
                + f'<section id="plan-detail" class="wrap"><h2>Forecasts in detail</h2>{parts["plan_rest"]}</section>'
                + parts["data"])
    return f"""
<header class="cover-7s">
  <div class="wrap">
    <div class="topbar"><div class="logo-7s" aria-hidden="true">{_logo()}</div>
    <button class="theme-btn" type="button">Theme: auto</button></div>
    <div class="eyebrow">Post-race analysis</div>
    <h1>{H.esc(a.race_name)}</h1>
    <p class="sub">{H.esc(a.boat)} · {H.esc(date)}</p>
    <p class="prepared">Prepared by {H.esc(s["name"])} · {H.esc(s["address"])} ·
    <a href="https://{s["web"]}">{s["web"]}</a> · <a href="mailto:{s["email"]}">{s["email"]}</a></p>
  </div>
</header>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main>
{skipper}
<section id="appendix" class="wrap appendix-head">
  <h2>Navigator appendix</h2>
  <p class="lede">The detail behind the pages above: phases, speed against the polar, instrument checks, and the
  forecasts model by model. Data: {H.esc(a.boat)}'s own log and routings, the public YB tracker and the official
  results.</p>
</section>
{appendix}
<footer class="wrap">
  <p>{H.esc(s["name"])} · {H.esc(s["address"])} · {s["web"]} · {s["email"]}</p>
  <p>Coastline: Natural Earth (public domain) and © OpenStreetMap contributors (ODbL). Analysis by Day After.</p>
</footer>
</main>"""
