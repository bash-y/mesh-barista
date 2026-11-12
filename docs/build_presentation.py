#!/usr/bin/env python3
"""Builds docs/presentation.html and docs/Mesh-Barista-Presentation.pdf (7 slides, 16:9).
Needs Python 3.12+, Playwright, the qrcode package and Chrome:  python3 docs/build_presentation.py
Chrome elsewhere (macOS): CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" python3 docs/build_presentation.py
Fonts (Space Grotesk, Inter, JetBrains Mono) load from Google Fonts, so the build needs internet."""
import os, re
from pathlib import Path

import qrcode
import qrcode.image.svg

# Pump flow rate: still the firmware default (FLOW_ML_PER_S on Node 1), not yet measured.
# Once measured, put the real number here, drop the "~" and "estimated" wording on slide 6, and rebuild.
FLOW_ML_S = 20
POUR_ML = 60

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


def qr_svg(data, label):
    """QR code as inline SVG: dark modules on a light tile, sized by CSS."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=3,
                       image_factory=qrcode.image.svg.SvgPathImage)
    qr.add_data(data)
    qr.make(fit=True)
    svg = qr.make_image().to_string(encoding="unicode")
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)  # let CSS size it
    svg = re.sub(r'\sid="[^"]*"', "", svg)  # two QR codes on one page: no duplicate ids
    svg = svg.replace("<svg", f'<svg class="qr" role="img" aria-label="QR code: {label}"', 1)
    return svg.replace('fill="#000000"', f'fill="{DARK}"')


def card(label, title, items, cls=""):
    lis = "".join(f"<li>{x}</li>" for x in items)
    return f'<div class="card {cls}"><div class="label">{label}</div><h3>{title}</h3><ul>{lis}</ul></div>'



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

# 3 · Architecture: system design diagram (inline SVG, units = pt)
WATER = "#8fb8e8"
NODE_W, GAP, NODE_Y, NODE_H = 330, 129, 104, 290
NODES = [
    ("Node 1 · Source", "Pump station", ["3 reservoir level sensors", "3 relays → 3 pumps", "Buzzer: gurgle while pouring", "Order queue (up to 7)", "Fail-safe + watchdog: pumps off"]),
    ("Node 2 · Gateway", "Control center", ["Joystick + OLED menu", "Buzzer alarm, jazz while pouring", "USB serial dashboard", "Relays Node 1 ↔ Node 3"]),
    ("Node 3 · Distribution", "Output", ["Cup level sensor", "Status OLED", "RGB LED: pump · ready · error"]),
]


def node_svg(i, label, title, items):
    x = i * (NODE_W + GAP)
    out = [f'<rect x="{x}" y="{NODE_Y}" width="{NODE_W}" height="{NODE_H}" rx="12" class="sd-node"/>',
           f'<text x="{x + 22}" y="{NODE_Y + 34}" class="sd-label">{label.upper()}</text>',
           f'<text x="{x + 22}" y="{NODE_Y + 68}" class="sd-title">{title}</text>']
    for j, item in enumerate(items):
        cy = NODE_Y + 88 + j * 39
        out.append(f'<rect x="{x + 18}" y="{cy}" width="{NODE_W - 36}" height="32" rx="6" class="sd-chip"/>'
                   f'<text x="{x + 32}" y="{cy + 22}" class="sd-item">{item}</text>')
    return "".join(out)


def link_svg(i):
    x0 = (i + 1) * NODE_W + i * GAP + 14
    x1 = x0 + GAP - 28
    y = NODE_Y + 120
    return (f'<path d="M{x0} {y}H{x1 - 14}" class="sd-mesh"/><path d="M{x1} {y}l-16 -9v18z" fill="{MINT}"/>'
            f'<path d="M{x1} {y + 26}H{x0 + 14}" class="sd-mesh"/><path d="M{x0} {y + 26}l16 -9v18z" fill="{MINT}"/>'
            f'<text x="{(x0 + x1) / 2}" y="{y + 60}" class="sd-mesh-t" text-anchor="middle">ESP-NOW</text>'
            f'<text x="{(x0 + x1) / 2}" y="{y + 84}" class="sd-mesh-s" text-anchor="middle">no router</text>')


c1, c3 = NODE_W / 2, 2 * (NODE_W + GAP) + NODE_W / 2
bottom = NODE_Y + NODE_H
centers = [i * (NODE_W + GAP) + NODE_W / 2 for i in range(3)]
DIAGRAM = f'''<svg class="sd" viewBox="0 0 1248 540" role="img" aria-label="System design: phones reach the dashboard on every node over Wi-Fi; three ESP32 nodes linked by ESP-NOW; water flows from the reservoirs through the pumps to the cup, and the cup level goes back to Node 1 to stop the pump.">
<rect x="0" y="0" width="1248" height="54" rx="10" class="sd-wifi"/>
<text x="624" y="34" class="sd-wifi-t" text-anchor="middle">Phones on Wi-Fi “{WIFI_SSID}” → {DASHBOARD_URL} · every node is an access point serving the same dashboard</text>
{"".join(f'<path d="M{cx} 54V{NODE_Y}" class="sd-wifi-l"/>' for cx in centers)}
{"".join(node_svg(i, *n) for i, n in enumerate(NODES))}
{link_svg(0)}{link_svg(1)}
<path d="M{c3} {bottom}V{bottom + 46}H{c1}V{bottom + 14}" class="sd-ctl"/><path d="M{c1} {bottom + 2}l-9 16h18z" fill="{AMBER}"/>
<text x="624" y="{bottom + 36}" class="sd-ctl-t" text-anchor="middle">cup at 90 % → Node 1 stops the pump (relayed if out of range)</text>
<rect x="0" y="{bottom + 76}" width="{NODE_W}" height="58" rx="10" class="sd-tank"/>
<text x="{c1}" y="{bottom + 112}" class="sd-tank-t" text-anchor="middle">Reservoirs: coffee · milk · cream</text>
<rect x="{c3 - NODE_W / 2}" y="{bottom + 76}" width="{NODE_W}" height="58" rx="10" class="sd-tank"/>
<text x="{c3}" y="{bottom + 112}" class="sd-tank-t" text-anchor="middle">Cup (destination tank)</text>
<path d="M{NODE_W + 14} {bottom + 105}H{c3 - NODE_W / 2 - 26}" class="sd-water"/><path d="M{c3 - NODE_W / 2 - 6} {bottom + 105}l-22 -12v24z" fill="{WATER}"/>
<text x="624" y="{bottom + 95}" class="sd-water-t" text-anchor="middle">pump → tubing (dyed water)</text>
</svg>'''

SLIDES.append(("dark", f'''
<h2>System architecture</h2>
{DIAGRAM}'''))

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
         (f"~{FLOW_ML_S} mL/s", "estimated pump flow rate (firmware default, not yet measured on hardware)"),
         (f"{POUR_ML} mL", f"per pour, run as a {POUR_ML / FLOW_ML_S:g} s timed pump burst at that estimate")]
stats = "".join(f'<div class="stat"><div class="num">{n}</div><div class="what">{w}</div></div>' for n, w in STATS)
SLIDES.append(("light", f'''
<h2>Results and demonstration</h2>
<div class="s6">
  <div>
    <div class="demo">
      <div class="label">Live demo — order a drink</div>
      <ol class="demo-body">
        <li><div class="qr-tile">{qr_svg(WIFI_QR, f"join the Wi-Fi {WIFI_SSID}")}</div>
          <p>Scan to join <b>{WIFI_SSID}</b>, then turn mobile data off</p></li>
        <li><div class="qr-tile">{qr_svg(DASHBOARD_URL, f"open {DASHBOARD_URL}")}</div>
          <p>Scan to open <b>{DASHBOARD_URL.removeprefix("http://")}</b> and order</p></li>
      </ol>
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
.sd {{ display: block; width: 1248pt; height: 540pt; margin-top: -8pt; }}
.sd text {{ font-family: 'Inter', sans-serif; }}
.sd-node {{ fill: {DARK_CARD}; stroke: {DARK_LINE}; stroke-width: 1; }}
.sd-chip {{ fill: {DARK}; stroke: {DARK_LINE}; stroke-width: 1; }}
.sd .sd-label {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; letter-spacing: 2.4px; fill: {AMBER}; }}
.sd .sd-title {{ font-family: 'Space Grotesk', sans-serif; font-weight: 500; font-size: 25px; fill: {CREAM}; }}
.sd-item {{ font-size: 17px; fill: {CREAM_MUTED}; }}
.sd-wifi {{ fill: {DARK_CARD}; stroke: {CREAM_MUTED}; stroke-width: 1; stroke-dasharray: 5 5; }}
.sd-wifi-t {{ font-size: 18px; fill: {CREAM}; }}
.sd-wifi-l {{ stroke: {CREAM_MUTED}; stroke-width: 2; stroke-dasharray: 5 5; }}
.sd-mesh {{ stroke: {MINT}; stroke-width: 5; }}
.sd .sd-mesh-t {{ font-family: 'JetBrains Mono', monospace; font-size: 15px; letter-spacing: 1px; fill: {MINT}; }}
.sd-mesh-s {{ font-size: 15px; fill: {CREAM_MUTED}; }}
.sd-ctl {{ fill: none; stroke: {AMBER}; stroke-width: 3; stroke-dasharray: 9 6; }}
.sd-ctl-t {{ font-size: 17px; fill: {AMBER}; }}
.sd-tank {{ fill: {DARK_CARD}; stroke: #8fb8e8; stroke-width: 1.5; }}
.sd-tank-t {{ font-size: 18px; fill: {CREAM}; }}
.sd-water {{ stroke: #8fb8e8; stroke-width: 7; }}
.sd-water-t {{ font-size: 17px; fill: #8fb8e8; }}

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
.demo-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 26pt; counter-reset: n; }}
.demo-body li {{ counter-increment: n; }}
.qr-tile {{ background: #ffffff; border-radius: 8pt; aspect-ratio: 1; }}
.qr {{ width: 100%; height: 100%; display: block; }}
.demo-body p {{ position: relative; padding-left: 34pt; margin: 14pt 0 0; font-size: 18pt; line-height: 1.35; color: {CREAM_MUTED}; }}
.demo-body b {{ color: {CREAM}; font-weight: 600; }}
.demo-body p::before {{ content: counter(n); position: absolute; left: 0; top: 1pt; width: 23pt; height: 23pt; border-radius: 50%; background: {AMBER}; color: {DARK}; font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 13pt; line-height: 23pt; text-align: center; }}
.caption {{ font-size: 19.5pt; line-height: 1.38; color: {MUTED}; margin: 14pt 0 0; }}
.stats {{ display: grid; grid-template-columns: auto 1fr; column-gap: 28pt; align-content: space-between; height: 468pt; padding-top: 14pt; }}
.stat {{ display: grid; grid-column: 1 / -1; grid-template-columns: subgrid; align-items: center; }}
.num {{ font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 66pt; line-height: 0.9; color: {COPPER}; letter-spacing: -1pt; }}
.num {{ white-space: nowrap; }}
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
