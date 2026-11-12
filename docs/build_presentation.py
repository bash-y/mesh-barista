#!/usr/bin/env python3
"""Builds docs/presentation.html and docs/Mesh-Barista-Presentation.pdf (7 slides, 16:9).
Needs Python 3.12+, Playwright, the qrcode package and Chrome:  python3 docs/build_presentation.py
Chrome elsewhere (macOS): CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" python3 docs/build_presentation.py
Fonts (Space Grotesk, Inter, JetBrains Mono) load from Google Fonts, so the build needs internet."""
import os, re
from pathlib import Path

import qrcode
import qrcode.image.svg

# Hardware measurements still to be taken. Fill these in, then rebuild.
POUR_ERROR_ML = "[__]"   # measured error on a 60 mL pour
FLOW_ML_S = "[__]"       # measured pump flow rate used for timed pours

WIFI_SSID = "Bashy"
WIFI_QR = f"WIFI:T:nopass;S:{WIFI_SSID};;"
DASHBOARD_URL = "http://barista.io"
TOTAL = 7

HERE = Path(__file__).resolve().parent

# Palette (sampled from the original deck)
DARK, DARK_CARD, DARK_LINE = "#1c1410", "#2a1f18", "#4a382b"
CREAM, CREAM_MUTED = "#f4ece0", "#c9b8a3"
AMBER, MINT, GREEN, CORAL = "#d9903d", "#5cc8ba", "#7fd39a", "#f08a7a"
PAPER, CARD, INK, MUTED, LINE = "#f4ece0", "#fffaf2", "#24180f", "#6b5847", "#dccdb8"
COPPER, TEAL, CODE_BG = "#8f4e0c", "#0f6b61", "#f4ece0"


def wifi_qr_svg():
    """Wi-Fi join QR as inline SVG: dark modules on a light tile, sized by CSS."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=3,
                       image_factory=qrcode.image.svg.SvgPathImage)
    qr.add_data(WIFI_QR)
    qr.make(fit=True)
    svg = qr.make_image().to_string(encoding="unicode")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)  # let CSS size it
    svg = svg.replace("<svg", f'<svg class="qr" role="img" aria-label="QR code: join the Wi-Fi {WIFI_SSID}"', 1)
    return svg.replace('fill="#000000"', f'fill="{DARK}"')


def card(label, title, items, cls=""):
    lis = "".join(f"<li>{x}</li>" for x in items)
    return f'<div class="card {cls}"><div class="label">{label}</div><h3>{title}</h3><ul>{lis}</ul></div>'


ARROWS = '''<div class="link"><svg viewBox="0 0 84 70" width="84" height="70"><path d="M0 12H66" stroke="{c}" stroke-width="5"/><path d="M84 12L64 2V22z" fill="{c}"/>
<path d="M84 58H18" stroke="{c}" stroke-width="5"/><path d="M0 58L20 48V68z" fill="{c}"/></svg><span>ESP-NOW</span></div>'''.format(c=MINT)

SLIDES = []

# 1 · Title
SLIDES.append(("dark title", f'''
<div class="kicker">ENGR 4399 · Cyber-Physical &amp; IoT Systems · Project 2</div>
<h1 class="hero">Mesh<br><span>Barista</span></h1>
<p class="tagline">A distributed, resilient pump control system that pours a measured cup of coffee, milk and cream.</p>
<div class="byline"><div><div class="team">Team</div><div class="names">Sebastian Cadena · Daniel Critchlow Jr</div></div>
<div class="date">November 12, 2026</div></div>'''))

# 2 · Problem
SLIDES.append(("light", '''
<h2>Problem and motivation</h2>
<div class="s2">
  <div class="s2-left"><p class="big">A pump that keeps running after it loses contact with its tank <em>wastes water and destroys itself.</em></p>
  <p class="sub">Project 1 put every decision in one ESP32 and a cloud API. Real water systems are spread out, and nodes fail without warning.</p></div>
  <div class="grid4">
    <div class="pcard"><h3>Dry-running pumps</h3><p>An empty source tank burns out the pump.</p></div>
    <div class="pcard"><h3>Overflow</h3><p>A full destination tank means water on the floor.</p></div>
    <div class="pcard"><h3>Silent failures</h3><p>Operators cannot tell which zone went down.</p></div>
    <div class="pcard"><h3>Single point of failure</h3><p>One controller or router takes the whole system with it.</p></div>
  </div>
</div>
<p class="model">Our model of it: three reservoirs are the source tanks, the cup is the destination tank, and dyed water stands in for the drinks.</p>'''))

# 3 · Architecture
SLIDES.append(("dark", f'''
<h2>System architecture</h2>
<div class="arch">
{card("Node 1 · Source / Pump", "Pump station", ["3 reservoir level sensors", "3 relays driving 3 pumps", "Buzzer: coffee machine gurgle while pouring", "Own fail-safe: pumps off", "Watchdog: a frozen program resets with pumps off"])}
{ARROWS}
{card("Node 2 · Gateway", "Control center", ["Joystick menu and OLED", "Buzzer alarm", "Jazz melody while pouring", "USB serial dashboard", "Relays Node 1 and Node 3"])}
{ARROWS}
{card("Node 3 · Distribution", "Output", ["Cup level sensor", "Status OLED", "RGB LED: pump, ready, error", "Its reading stops the pump"])}
</div>
<div class="opview"><div class="label">Operator view</div><p>Every node is a Wi-Fi access point that hosts the same web dashboard, so it survives the loss of any one node.</p></div>
<p class="note">No router, cloud service or API is needed: each node that owns an actuator decides locally.</p>'''))

# 4 · Technical implementation
JSON = '''{"node":1,"seq":145,
 "zone":"pump station",
 "up":80925,"pump":0,
 "lvl":[77,50,77],
 "state":"SAFE",
 "why":"lost Node 2"}'''
SLIDES.append(("light", f'''
<h2>Technical implementation</h2>
<div class="cols3">
  {card("Wireless", "ESP-NOW with our own relay", ["Broadcast frames: no router, no pairing.", "Sequence numbers drop repeats.", "A node rebroadcasts what it hears once, so a node out of range is still reached.", "Heartbeat every second; lost after 3 s."])}
  <div class="card"><div class="label">Data</div><h3>JSON messages</h3><pre>{JSON}</pre><ul><li>Largest message (a full order queue) is about 225 bytes; one frame holds 250.</li></ul></div>
  {card("Interface", "Dashboard on every node", ["Each ESP32 serves the page and a JSON status feed over HTTP.", "Shows nodes alive or lost, levels, pump state, event log and mesh paths.", "Test buttons run pumps, buzzers and the LED.", f"<b>Order queue:</b> anyone in the room joins the open “{WIFI_SSID}” Wi-Fi and orders a drink from their phone; the operator pours orders in turn with the joystick or the dashboard."])}
</div>'''))

# 5 · Sustainability logic
RULES = [("Dry-run lock", "below 10 %, unlock above 20 %", "The pump; the gap stops relay chatter"),
         ("Overflow stop", "cup at 90 %, read by Node 3", "No spilled water"),
         ("Stale data stop", "no cup reading for 1.5 s", "Never pour blind"),
         ("Lost node", "no heartbeat for 3 s", "Pumps off, buzzer, zone flagged"),
         ("Leave SAFE", "operator acknowledge", "A half-poured cup is an unknown state")]
rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in RULES)
SLIDES.append(("dark", f'''
<h2>Sustainability logic</h2>
<div class="s5">
  <table><thead><tr><th>Rule</th><th>Threshold</th><th>What it protects</th></tr></thead><tbody>{rows}</tbody></table>
  <div class="states">
    <div class="state"><b style="color:{GREEN}">NORMAL</b><p>All nodes alive. Pours allowed.</p></div>
    <div class="state"><b style="color:{AMBER}">DEGRADED</b><p>A reservoir is low, or running without Node 2.</p></div>
    <div class="state"><b style="color:{CORAL}">SAFE</b><p>Pumps off, buzzers on, LED flashing red.</p></div>
  </div>
</div>'''))

# 6 · Results and demonstration (live demo)
STATS = [("18 / 18", "control and fault scenarios passed in simulation, including each node lost in turn"),
         ("3 s", "to flag a lost node and name its zone on the dashboard"),
         (f"{POUR_ERROR_ML} mL", "measured error on a 60 mL pour, hardware"),
         (f"{FLOW_ML_S} mL/s", "measured pump flow rate used for timed pours")]
stats = "".join(f'<div class="stat"><div class="num">{n}</div><div class="what">{w}</div></div>' for n, w in STATS)
SLIDES.append(("light", f'''
<h2>Results and demonstration</h2>
<div class="s6">
  <div>
    <div class="demo">
      <div class="label">Live demo — order a drink</div>
      <div class="demo-body">
        <div class="qr-tile">{wifi_qr_svg()}</div>
        <ol>
          <li>Join the Wi-Fi <b>{WIFI_SSID}</b> (no password)</li>
          <li>Turn mobile data off</li>
          <li>Open <b>{DASHBOARD_URL}</b></li>
          <li>Order</li>
        </ol>
      </div>
    </div>
    <p class="caption">Order from your phone, watch it pour, stop on a full cup, then pull a node and watch SAFE.</p>
  </div>
  <div class="stats">{stats}</div>
</div>'''))

# 7 · Lessons learned
SLIDES.append(("dark", f'''
<h2>Lessons learned and improvements</h2>
<div class="s7">
  {card("What was hard", "Engineering challenges", [
      "A full mesh library was more than three nodes needed; ESP-NOW with a small relay was simpler to reason about.",
      "A clicking relay does not prove the pump has power: the pump circuit needs its own test.",
      "A joystick does not rest at mid-scale, so it is calibrated at boot.",
      "Raw pin readings found GPIO 34 tied to ground, even with a new joystick; the X axis moved to GPIO 32.",
      "Electrical noise from the cream pump froze Node 1 with its relay closed; a watchdog now resets it into SAFE with every pump off.",
      "Passive buzzers are silent on a plain on/off signal; the alarm needed a real tone.",
      "The cup sensor’s 2″ strips cover only part of a 4.5″ cup and are not linear, so every sensor uses a multi-point calibration."], "hard")}
  {card("What comes next", "Future enhancements", [
      "Load cell under the cup to pour by weight.",
      "Servo pinch valve so SAFE also closes the outlet.",
      "Flow check that catches a blocked tube or empty line.",
      "Encrypted ESP-NOW and a login on the dashboard."], "next")}
</div>'''))

CSS = f"""
@page {{ size: 1440pt 810pt; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: 'Inter', sans-serif; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.slide {{ width: 1440pt; height: 810pt; position: relative; overflow: hidden; padding: 96pt 96pt 0; page-break-after: always; break-after: page; }}
.slide:last-child {{ page-break-after: auto; break-after: auto; }}
.dark {{ background: {DARK}; color: {CREAM}; }}
.light {{ background: {PAPER}; color: {INK}; }}
h2 {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; font-size: 54.5pt; line-height: 1; letter-spacing: -0.2pt; margin: 4pt 0 0; height: 91pt; }}
h3 {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; font-size: 25.5pt; line-height: 1.2; margin: 0; }}
.label {{ font-family: 'JetBrains Mono', monospace; font-size: 15.75pt; letter-spacing: 2.85pt; text-transform: uppercase; }}
.foot {{ position: absolute; left: 96pt; bottom: 48pt; font-family: 'JetBrains Mono', monospace; font-size: 16pt; letter-spacing: 1.15pt; }}
.dark .foot {{ color: {CREAM_MUTED}; }} .light .foot {{ color: {MUTED}; }}
ul, ol {{ margin: 0; padding: 0; list-style: none; }}

/* cards */
.card {{ border-radius: 12pt; padding: 26pt 27pt; }}
.dark .card {{ background: {DARK_CARD}; border: 1pt solid {DARK_LINE}; }}
.light .card {{ background: {CARD}; border: 1pt solid {LINE}; }}
.card .label {{ margin: 0 0 11pt; }}
.dark .card .label {{ color: {AMBER}; }} .light .card .label {{ color: {COPPER}; }}
.card h3 {{ margin-bottom: 9pt; }}
.card li {{ font-size: 19.5pt; line-height: 1.38; margin-bottom: 9.5pt; }}
.dark .card li {{ color: {CREAM_MUTED}; }} .light .card li {{ color: {MUTED}; }}
.card li b {{ font-weight: 600; }} .light .card li b {{ color: {INK}; }}

/* 1 */
.title {{ padding-top: 96pt; }}
.kicker {{ font-family: 'JetBrains Mono', monospace; font-size: 18.4pt; letter-spacing: 4.6pt; text-transform: uppercase; color: {AMBER}; margin-top: 0; }}
.hero {{ font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 112pt; line-height: 1.045; letter-spacing: -1pt; margin: 92pt 0 0; }}
.hero span {{ color: {AMBER}; }}
.tagline {{ font-size: 32.5pt; line-height: 1.32; color: {CREAM_MUTED}; max-width: 900pt; margin: 22pt 0 0; }}
.byline {{ position: absolute; left: 96pt; right: 96pt; top: 643pt; display: flex; justify-content: space-between; align-items: flex-end; }}
.team {{ font-family: 'JetBrains Mono', monospace; font-size: 16pt; letter-spacing: 3.7pt; text-transform: uppercase; color: {MINT}; margin-bottom: 4pt; }}
.names {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; font-size: 33pt; }}
.date {{ font-family: 'JetBrains Mono', monospace; font-size: 21pt; color: {CREAM_MUTED}; padding-bottom: 0; transform: translateY(-2pt); }}

/* 2 */
.s2 {{ display: grid; grid-template-columns: 470pt 1fr; gap: 38pt; align-items: center; height: 406pt; }}
.big {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; font-size: 34.5pt; line-height: 1.25; margin: 0; }}
.big em {{ font-style: normal; color: {COPPER}; }}
.sub {{ font-size: 20pt; line-height: 1.42; color: {MUTED}; margin: 18pt 0 0; }}
.grid4 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 19pt 19pt; }}
.pcard {{ background: {CARD}; border: 1pt solid {LINE}; border-radius: 12pt; height: 194pt; padding: 28pt 27pt; }}
.pcard h3 {{ margin-bottom: 12pt; }}
.pcard p {{ margin: 0; font-size: 19.5pt; line-height: 1.35; color: {MUTED}; }}
.model {{ color: {TEAL}; font-weight: 600; font-size: 21pt; line-height: 1.33; margin: 30pt 0 0; }}

/* 3 */
.arch {{ display: grid; grid-template-columns: 1fr 112pt 1fr 112pt 1fr; align-items: stretch; }}
.arch .card {{ padding: 26pt 27pt 18pt; }}
.arch .card li {{ font-size: 19.5pt; line-height: 1.3; margin-bottom: 9pt; }}
.link {{ display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 95pt; }}
.link svg {{ width: 84pt; height: 70pt; }}
.link span {{ position: absolute; margin-top: 23pt; font-family: 'JetBrains Mono', monospace; font-size: 16.3pt; letter-spacing: 1pt; color: {MINT}; }}
.opview {{ margin-top: 22pt; border: 1pt solid {MINT}; background: {DARK_CARD}; border-radius: 12pt; padding: 22pt 27pt; display: grid; grid-template-columns: 243pt 1fr; align-items: center; }}
.opview .label {{ color: {MINT}; }}
.opview p {{ margin: 0; font-size: 21pt; line-height: 1.4; color: {CREAM}; }}
.note {{ font-size: 19.5pt; color: {CREAM_MUTED}; margin: 22pt 0 0; }}

/* 4 */
.cols3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 21pt; height: 499pt; }}
.cols3 .card li {{ margin-bottom: 9.5pt; }}
pre {{ font-family: 'JetBrains Mono', monospace; font-size: 18pt; line-height: 1.45; color: {INK}; background: {CODE_BG}; border-radius: 9pt; padding: 13pt 15pt; margin: 0 0 12pt; }}

/* 5 */
.s5 {{ display: grid; grid-template-columns: 810pt 1fr; gap: 42pt; align-items: start; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 16.2pt; letter-spacing: 1.1pt; text-transform: uppercase; color: {AMBER}; text-align: left; padding: 13pt 0 15pt; border-bottom: 1pt solid {DARK_LINE}; }}
td {{ font-size: 19.5pt; line-height: 1.35; padding: 12pt 12pt 12pt 0; border-bottom: 1pt solid {DARK_LINE}; color: {CREAM_MUTED}; vertical-align: middle; }}
td:first-child {{ color: {CREAM}; font-weight: 600; width: 152pt; }}
td:nth-child(2) {{ color: {MINT}; width: 300pt; }}
.states {{ display: flex; flex-direction: column; gap: 16pt; }}
.state {{ background: {DARK_CARD}; border: 1pt solid {DARK_LINE}; border-radius: 10pt; padding: 20pt 23pt 20pt; }}
.state b {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 25.5pt; display: block; }}
.state p {{ margin: 2pt 0 0; font-size: 19.5pt; line-height: 1.35; color: {CREAM_MUTED}; }}

/* 6 */
.s6 {{ display: grid; grid-template-columns: 570pt 1fr; gap: 50pt; }}
.demo {{ background: {DARK}; border-radius: 14pt; padding: 22pt 26pt 26pt; color: {CREAM}; }}
.demo .label {{ color: {AMBER}; margin-bottom: 16pt; }}
.demo-body {{ display: flex; gap: 26pt; align-items: center; }}
.qr-tile {{ flex: none; background: #ffffff; border-radius: 8pt; padding: 0; width: 250pt; height: 250pt; }}
.qr {{ width: 250pt; height: 250pt; display: block; }}
.demo ol {{ counter-reset: n; }}
.demo li {{ counter-increment: n; position: relative; padding-left: 34pt; font-size: 19pt; line-height: 1.35; margin: 0 0 14pt; color: {CREAM_MUTED}; }}
.demo li b {{ color: {CREAM}; font-weight: 600; }}
.demo li::before {{ content: counter(n); position: absolute; left: 0; top: 1pt; width: 23pt; height: 23pt; border-radius: 50%; background: {AMBER}; color: {DARK}; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13pt; line-height: 23pt; text-align: center; }}
.caption {{ font-size: 19.5pt; line-height: 1.38; color: {MUTED}; margin: 14pt 0 0; }}
.stats {{ display: flex; flex-direction: column; justify-content: space-between; height: 468pt; padding-top: 14pt; }}
.stat {{ display: grid; grid-template-columns: 245pt 1fr; align-items: center; }}
.num {{ font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 66pt; line-height: 0.9; color: {COPPER}; letter-spacing: -1pt; }}
.num {{ max-width: 215pt; }}
.what {{ font-size: 21pt; line-height: 1.3; color: {INK}; }}

/* 7 */
.s7 {{ display: grid; grid-template-columns: 1.55fr 1fr; gap: 24pt; height: 499pt; }}
.s7 .next .label {{ color: {MINT}; }}
.s7 .card li {{ font-size: 20.25pt; line-height: 1.38; margin-bottom: 10pt; }}
.s7 .hard li {{ font-size: 18.25pt; line-height: 1.34; margin-bottom: 8.5pt; }}
"""


def build_html():
    secs = []
    for i, (cls, body) in enumerate(SLIDES, 1):
        foot = "" if i == 1 else f'<div class="foot">MESH BARISTA · ENGR 4399 PROJECT 2 · {i} / {TOTAL}</div>'
        secs.append(f'<section class="slide {cls}">{body}{foot}</section>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Mesh Barista · Project 2</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@500;600;700&display=block" rel="stylesheet">
<style>{CSS}</style></head><body>
{chr(10).join(secs)}
</body></html>"""


if __name__ == "__main__":
    html_path = HERE / "presentation.html"
    html_path.write_text(build_html())
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
        pg = b.new_page()
        pg.goto("file://" + str(html_path), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        missing = pg.evaluate("""() => ['Inter', 'Space Grotesk', 'JetBrains Mono']
            .filter(f => !document.fonts.check(`16px "${f}"`))""")
        if missing:
            raise SystemExit(f"fonts did not load: {missing}")
        pg.pdf(path=str(HERE / "Mesh-Barista-Presentation.pdf"), width="1920px", height="1080px",
               print_background=True, prefer_css_page_size=True,
               margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print("built")
