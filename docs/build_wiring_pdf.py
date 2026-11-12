#!/usr/bin/env python3
"""Builds docs/wiring-guide.html and ../Mesh-Barista-Wiring-Guide.pdf.
Needs Playwright and Chrome:  python3 docs/build_wiring_pdf.py"""
import html, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESP, CREAM, COPPER, TEAL, INK, MUTED, LINE = "#1c1410", "#f4ece0", "#b8651b", "#0f6b61", "#24180f", "#6b5847", "#dccdb8"
POWER = {"3V3": "#d23f3f", "VIN (5V)": "#e58a1f", "GND": "#1b1b1b"}
SIGNAL = ["#1f77b4", "#8e44ad", "#0f8f7f", "#c2185b", "#5d6d1e", "#3949ab", "#00838f", "#a0522d"]


def diagram(esp_pins, parts, row=21):
    """esp_pins: ESP32 pin names, top to bottom. parts: [(title, [(part pin, esp pin), ...]), ...]."""
    x_esp, x_part, w = 190, 470, 700
    y, boxes = 14, []
    for title, pins in parts:
        boxes.append((title, pins, y))
        y += 26 + row * len(pins) + 12
    height = y + 4
    span = height - 60
    esp_y = {p: 44 + (i + 0.5) * span / len(esp_pins) for i, p in enumerate(esp_pins)}
    lane = {p: x_esp + 34 + i * (x_part - x_esp - 68) / max(1, len(esp_pins) - 1) for i, p in enumerate(esp_pins)}
    color, sig = {}, 0
    for p in esp_pins:
        if p in POWER: color[p] = POWER[p]
        else: color[p] = SIGNAL[sig % len(SIGNAL)]; sig += 1
    o = [f'<svg viewBox="0 0 {w} {height}" width="100%" role="img" aria-label="Connection diagram">']
    o.append(f'<rect x="20" y="14" width="{x_esp-20}" height="{height-28}" rx="12" fill="{ESP}"/>')
    o.append(f'<text x="{(x_esp+20)/2}" y="36" text-anchor="middle" fill="{CREAM}" font-size="13" font-weight="700" letter-spacing="2">ESP32</text>')
    for p in esp_pins:
        o.append(f'<circle cx="{x_esp}" cy="{esp_y[p]}" r="4.5" fill="{color[p]}" stroke="{CREAM}" stroke-width="1.5"/>')
        o.append(f'<text x="{x_esp-12}" y="{esp_y[p]+4}" text-anchor="end" fill="{CREAM}" font-size="12.5" font-family="monospace" font-weight="600">{html.escape(p)}</text>')
    trunk = {p: [esp_y[p]] for p in esp_pins}
    for title, pins, top in boxes:
        h = 26 + row * len(pins)
        o.append(f'<rect x="{x_part}" y="{top}" width="{w-x_part-14}" height="{h}" rx="9" fill="#fffaf2" stroke="{LINE}" stroke-width="1.3"/>')
        o.append(f'<text x="{x_part+14}" y="{top+18}" fill="{INK}" font-size="12.5" font-weight="700">{html.escape(title)}</text>')
        for i, (pp, ep) in enumerate(pins):
            py = top + 26 + row * i + row / 2 - 2
            trunk[ep].append(py)
            o.append(f'<path d="M{lane[ep]} {py} H{x_part}" stroke="{color[ep]}" stroke-width="2.4" fill="none"/>')
            o.append(f'<circle cx="{x_part}" cy="{py}" r="4" fill="{color[ep]}"/>')
            o.append(f'<text x="{x_part+14}" y="{py+4}" fill="{MUTED}" font-size="12" font-family="monospace">{html.escape(pp)}</text>')
            o.append(f'<text x="{w-26}" y="{py+4}" text-anchor="end" fill="{color[ep]}" font-size="11.5" font-family="monospace" font-weight="700">{html.escape(ep)}</text>')
    for p in esp_pins:
        if len(trunk[p]) < 2: continue
        o.append(f'<path d="M{x_esp} {esp_y[p]} H{lane[p]}" stroke="{color[p]}" stroke-width="2.4" fill="none"/>')
        o.append(f'<path d="M{lane[p]} {min(trunk[p])} V{max(trunk[p])}" stroke="{color[p]}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    o.append("</svg>")
    return "\n".join(o)


PUMP_SVG = f'''<svg viewBox="0 0 700 250" width="100%" role="img" aria-label="Pump circuit">
<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#d23f3f"/></marker></defs>
<rect x="14" y="60" width="130" height="110" rx="10" fill="{ESP}"/><text x="79" y="100" text-anchor="middle" fill="{CREAM}" font-size="13" font-weight="700">PUMP SUPPLY</text>
<text x="132" y="86" text-anchor="end" fill="#ff9c9c" font-size="15" font-weight="700" font-family="monospace">+</text><text x="132" y="158" text-anchor="end" fill="{CREAM}" font-size="15" font-weight="700" font-family="monospace">−</text>
<rect x="230" y="40" width="150" height="84" rx="10" fill="#fffaf2" stroke="{LINE}" stroke-width="1.3"/><text x="305" y="60" text-anchor="middle" fill="{INK}" font-size="12.5" font-weight="700">RELAY</text>
<text x="244" y="86" fill="{MUTED}" font-size="12" font-family="monospace">COM</text><text x="366" y="86" text-anchor="end" fill="{MUTED}" font-size="12" font-family="monospace">NO</text>
<text x="305" y="112" text-anchor="middle" fill="{MUTED}" font-size="11">NC: leave empty</text>
<circle cx="560" cy="118" r="44" fill="#fffaf2" stroke="{LINE}" stroke-width="1.3"/><text x="560" y="114" text-anchor="middle" fill="{INK}" font-size="12.5" font-weight="700">PUMP</text><text x="560" y="130" text-anchor="middle" fill="{MUTED}" font-size="11">under water</text>
<path d="M144 82 H230" stroke="#d23f3f" stroke-width="2.6" fill="none" marker-end="url(#a)"/>
<path d="M380 82 H560 V74" stroke="#d23f3f" stroke-width="2.6" fill="none"/>
<path d="M560 162 V200 H180 V154 H144" stroke="#1b1b1b" stroke-width="2.6" fill="none"/>
<path d="M180 200 V232 H60" stroke="#1b1b1b" stroke-width="2.6" fill="none"/><text x="66" y="226" fill="{INK}" font-size="12" font-weight="700">to ESP32 GND</text>
<path d="M640 82 H560 M640 82 V200 H560" stroke="{COPPER}" stroke-width="2" fill="none" stroke-dasharray="5 4"/>
<path d="M628 150 h24 l-12 -18z" fill="{COPPER}"/><path d="M628 130 h24" stroke="{COPPER}" stroke-width="3"/>
<text x="660" y="128" fill="{COPPER}" font-size="11.5" font-weight="700">stripe</text><text x="660" y="142" fill="{COPPER}" font-size="11.5">toward +</text>
<text x="470" y="72" text-anchor="middle" fill="#d23f3f" font-size="11.5" font-weight="700">pump + (red)</text><text x="380" y="216" text-anchor="middle" fill="{INK}" font-size="11.5" font-weight="700">pump − (black)</text>
</svg>'''


def table(rows, head=("Part", "Part pin", "ESP32 pin")):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"

def checks(items): return '<ul class="check">' + "".join(f"<li><span class='box'></span><span>{x}</span></li>" for x in items) + "</ul>"
def steps(items): return '<ol class="steps">' + "".join(f"<li>{x}</li>" for x in items) + "</ol>"
def note(kind, title, text): return f'<div class="note {kind}"><b>{title}</b>{text}</div>'

N1 = diagram(["GPIO 25", "GPIO 26", "GPIO 27", "VIN (5V)", "GPIO 32", "GPIO 33", "GPIO 34", "3V3", "GPIO 13", "GND"], [
    ("Relay 1 · coffee", [("IN", "GPIO 25"), ("VCC", "VIN (5V)"), ("GND", "GND")]),
    ("Relay 2 · milk", [("IN", "GPIO 26"), ("VCC", "VIN (5V)"), ("GND", "GND")]),
    ("Relay 3 · cream", [("IN", "GPIO 27"), ("VCC", "VIN (5V)"), ("GND", "GND")]),
    ("Water sensor · coffee", [("S", "GPIO 32"), ("+", "3V3"), ("−", "GND")]),
    ("Water sensor · milk", [("S", "GPIO 33"), ("+", "3V3"), ("−", "GND")]),
    ("Water sensor · cream", [("S", "GPIO 34"), ("+", "3V3"), ("−", "GND")]),
    ("Buzzer", [("I/O", "GPIO 13"), ("VCC", "3V3"), ("GND", "GND")])], row=18)
N2 = diagram(["GPIO 34", "GPIO 35", "GPIO 27", "3V3", "GPIO 21", "GPIO 22", "GPIO 25", "GND"], [
    ("Joystick", [("VRx", "GPIO 34"), ("VRy", "GPIO 35"), ("SW", "GPIO 27"), ("+5V", "3V3"), ("GND", "GND")]),
    ("OLED display", [("SDA", "GPIO 21"), ("SCL", "GPIO 22"), ("VCC", "3V3"), ("GND", "GND")]),
    ("Buzzer", [("I/O", "GPIO 25"), ("VCC", "3V3"), ("GND", "GND")])])
N3 = diagram(["GPIO 32", "3V3", "GPIO 21", "GPIO 22", "GPIO 25", "GPIO 26", "GPIO 27", "GND"], [
    ("Water sensor · cup", [("S", "GPIO 32"), ("+", "3V3"), ("−", "GND")]),
    ("OLED display", [("SDA", "GPIO 21"), ("SCL", "GPIO 22"), ("VCC", "3V3"), ("GND", "GND")]),
    ("RGB LED (V G B R)", [("V", "3V3"), ("R", "GPIO 25"), ("G", "GPIO 26"), ("B", "GPIO 27")])])

def page(label, title, lead, body): return f'<section class="page"><p class="eyebrow">{label}</p><h1>{title}</h1><p class="lead">{lead}</p>{body}</section>'

DOC = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Mesh Barista Wiring Guide</title><style>
@page {{ size: Letter; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Helvetica, Arial, sans-serif; color: {INK}; font-size: 10.6pt; line-height: 1.45; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 8.5in; min-height: 11in; padding: 0.62in 0.7in 0.66in; page-break-after: always; position: relative; background: #fffdf9; }}
.cover {{ background: {ESP}; color: {CREAM}; display: flex; flex-direction: column; justify-content: space-between; padding: 0.9in 0.8in; height: 11in; }}
.cover h1 {{ font-size: 54pt; line-height: 1.02; margin: 0 0 14pt; color: {CREAM}; }} .cover h1 span {{ color: #d9903d; }}
.cover .sub {{ font-size: 16pt; color: #c9b8a3; max-width: 5.6in; line-height: 1.35; }}
.cover .eyebrow {{ color: #d9903d; }} .cover .meta {{ font-size: 11pt; color: #c9b8a3; line-height: 1.7; }} .cover .meta b {{ color: {CREAM}; }}
.toc {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6pt 30pt; font-size: 11.5pt; border-top: 1px solid #4a382b; padding-top: 16pt; }} .toc span {{ color: #5cc8ba; font-family: monospace; margin-right: 8pt; }}
.eyebrow {{ font-family: monospace; font-size: 9pt; letter-spacing: 2.5px; text-transform: uppercase; color: {COPPER}; margin: 0 0 6pt; font-weight: 700; }}
h1 {{ font-size: 24pt; margin: 0 0 6pt; line-height: 1.1; }} h2 {{ font-size: 13pt; margin: 12pt 0 5pt; color: {TEAL}; }}
.lead {{ font-size: 11.5pt; color: {MUTED}; margin: 0 0 12pt; max-width: 6.4in; }}
table {{ width: 100%; border-collapse: collapse; font-size: 10pt; margin: 4pt 0 8pt; break-inside: avoid; }}
th {{ text-align: left; font-size: 8pt; letter-spacing: 1.2px; text-transform: uppercase; color: {MUTED}; border-bottom: 1.5px solid {INK}; padding: 4pt 8pt 4pt 0; }}
td {{ padding: 4.5pt 8pt 4.5pt 0; border-bottom: 1px solid {LINE}; vertical-align: top; }} td:last-child, td:nth-child(2) {{ font-family: monospace; font-weight: 700; }} table.plain td {{ font-family: inherit; font-weight: 400; }} table.plain td:first-child {{ font-weight: 700; width: 34%; }}
.fig {{ border: 1px solid {LINE}; border-radius: 10pt; padding: 8pt 10pt 4pt; background: {CREAM}; margin: 6pt 0 8pt; break-inside: avoid; }} .fig p {{ margin: 0 0 4pt; font-size: 8.5pt; color: {MUTED}; }}
.note {{ border-left: 4pt solid {TEAL}; background: #e9f3f0; padding: 7pt 10pt; border-radius: 0 6pt 6pt 0; margin: 7pt 0; break-inside: avoid; }} .note b {{ display: block; font-size: 9.5pt; margin-bottom: 1pt; }}
.note.warn {{ border-color: #c0392b; background: #fbeceb; }} .note.tip {{ border-color: {COPPER}; background: #fbf1e3; }}
.steps {{ margin: 4pt 0; padding-left: 18pt; }} .steps li {{ margin: 3.5pt 0; padding-left: 3pt; }} .steps li::marker {{ font-weight: 700; color: {COPPER}; }}
.check {{ list-style: none; margin: 4pt 0; padding: 0; }} .check li {{ display: flex; gap: 8pt; margin: 3.6pt 0; break-inside: avoid; }} .box {{ flex: 0 0 11pt; height: 11pt; border: 1.4pt solid {INK}; border-radius: 2.5pt; margin-top: 1.5pt; }}
.cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 26pt; }} .rules {{ display: grid; grid-template-columns: 1fr 1fr; gap: 9pt; }} .rule {{ border: 1px solid {LINE}; border-radius: 8pt; padding: 9pt 11pt; background: #fff; }} .rule b {{ display: block; color: {COPPER}; margin-bottom: 2pt; }}
.key {{ display: flex; gap: 14pt; flex-wrap: wrap; font-size: 9pt; margin: 6pt 0 0; }} .key i {{ display: inline-block; width: 18pt; height: 3.5pt; border-radius: 2pt; vertical-align: middle; margin-right: 5pt; }}
code {{ font-family: monospace; background: {CREAM}; padding: 0 3pt; border-radius: 3pt; font-size: 9.6pt; }}
.foot {{ position: absolute; left: 0.7in; right: 0.7in; bottom: 0.38in; display: flex; justify-content: space-between; font-family: monospace; font-size: 8pt; color: {MUTED}; border-top: 1px solid {LINE}; padding-top: 5pt; }}
</style></head><body>

<section class="page cover">
<div><p class="eyebrow">ENGR 4399 · Project 2 · Wiring guide</p><h1>Mesh<br><span>Barista</span></h1>
<p class="sub">How to wire the three ESP32 nodes, check each part from the dashboard, and fix the common faults.</p></div>
<div><div class="toc">
<div><span>02</span>Before you start</div><div><span>06</span>Node 3: output</div>
<div><span>03</span>Node 1: control wiring</div><div><span>07</span>Power-up checklist</div>
<div><span>04</span>Node 1: pumps and water</div><div><span>08</span>Troubleshooting</div>
<div><span>05</span>Node 2: control center</div><div></div></div>
<p class="meta" style="margin-top:22pt"><b>Team</b> &nbsp;Sebastian Cadena · Daniel Critchlow Jr<br><b>Dashboard</b> &nbsp;join the nodes' Wi-Fi, then open http://barista.io</p></div>
</section>

{page("Before you start", "Parts and ground rules", "Build and test one node at a time. Unplug USB whenever you move a wire.", f'''
<div class="cols"><div><h2>Node 1 · pump station</h2>{checks(["ESP32 DevKit", "3 relay modules", "3 pumps and tubing", "3 water sensors", "1 buzzer (3-pin)", "Pump power supply", "3 diodes (1N4007)", "3 resistors, 10 kΩ (recommended)", "3 reservoir cups"])}</div>
<div><h2>Node 2 · control center</h2>{checks(["ESP32 DevKit", "Joystick module", "OLED, 0.96 in, 4-pin", "1 buzzer (3-pin)", "USB cable to a laptop"])}
<h2>Node 3 · output</h2>{checks(["ESP32 DevKit", "1 water sensor", "OLED, 0.96 in, 4-pin", "RGB LED, 4-pin (V G B R)", "Output cup"])}</div></div>
<h2>Four rules for every node</h2><div class="rules">
<div class="rule"><b>Signal parts run on 3V3</b>Water sensors, the joystick and the RGB LED go on the <code>3V3</code> pin, even where the part says <code>+5V</code>. More than 3.3 V into an ESP32 input can damage it.</div>
<div class="rule"><b>Only relays use 5 V</b>Relay modules take their power from the <code>VIN</code> (or <code>5V</code>) pin.</div>
<div class="rule"><b>All grounds join</b>Every part's GND goes to an ESP32 <code>GND</code> pin. On Node 1 the pump supply's negative goes there too.</div>
<div class="rule"><b>Pumps have their own supply</b>Never power a pump from an ESP32 pin. The relays switch the pump supply.</div></div>
<h2>Reading the diagrams</h2><p style="margin:0">Each line is one jumper wire from the ESP32 pin on the left to the part pin on the right. Pin names are GPIO numbers; most boards print them as <code>D25</code>, <code>D32</code> and so  on. Run 3V3 and GND to the breadboard's power rails first, so every part takes power from the rails.</p>
<div class="key"><span><i style="background:#d23f3f"></i>3V3 power</span><span><i style="background:#e58a1f"></i>5 V power (VIN)</span><span><i style="background:#1b1b1b"></i>Ground</span><span><i style="background:#1f77b4"></i><i style="background:#8e44ad"></i><i style="background:#0f8f7f"></i>Signal wires</span></div>
''')}

{page("Node 1 · step 1 of 2", "Pump station: control wiring", "The ESP32 side: relays, reservoir sensors and the buzzer. No pump power yet.", f'''
<div class="fig"><p>Node 1 connections</p>{N1}</div>
<div class="cols" style="gap:0 12pt">{note("", "Relay jumper", "If a relay module has an H/L jumper, set it to <b style='display:inline'>H</b> (active-HIGH).")}
{note("tip", "Pull-down resistors", "One 10 kΩ from each of GPIO 25, 26 and 27 to GND holds the relays off while the ESP32 resets.")}</div>''')}

{page("Node 1 · step 2 of 2", "Pump station: pumps and water", "The pump side never touches an ESP32 pin except ground. Repeat this circuit for each of the three relays.", f'''
<div class="fig"><p>One pump circuit</p>{PUMP_SVG}</div>
{steps(["Pump supply <b>+</b> to the relay's <b>COM</b> terminal.", "The relay's <b>NO</b> terminal to the pump's <b>+</b> wire (usually red). Leave <b>NC</b> empty.", "The pump's <b>−</b> wire (usually black) to pump supply <b>−</b>.", "Pump supply <b>−</b> to an ESP32 <b>GND</b> pin. One wire covers all three pumps.", "A diode across each pump's two wires, with the <b>striped end on the pump's + wire</b>."])}
{note("warn", "Check the diode direction", "A backwards diode shorts the supply the moment the relay closes. The relay clicks and the pump never runs.")}
{note("", "Why NO and not NC", "On NO, a pump only runs while the ESP32 is actively holding its relay on. A reset or power loss leaves every pump off.")}
<h2>Water and tubing</h2>{checks(["Each pump sits at the bottom of its reservoir. A submersible pump must be under water to pump.", "Each water sensor is clipped inside its reservoir, strips pointing down, electronics at the top kept dry.", "The three outlet tubes reach the cup on Node 3.", "A tray sits under everything to catch spills."])}''')}

{page("Node 2", "Control center", "The joystick picks the drink, the OLED shows the menu, and the buzzer sounds the alarm.", f'''
<div class="fig"><p>Node 2 connections</p>{N2}</div>
{note("warn", "Joystick power", "The joystick's power pin is labeled <code>+5V</code>, but it must go to <b style='display:inline'>3V3</b>.")}
{note("tip", "Hands off at power-up", "Node 2 measures where the joystick rests when it starts. Leave the stick alone for the first second.")}
<h2>Using the joystick</h2>{table([("Left / right", "Choose coffee, milk or cream"), ("Up / down", "Change the amount in 10 mL steps"), ("Click", "Pour. In SAFE, a click acknowledges instead")], ("Move", "What it does")).replace("<table>", '<table class="plain">')}
<p style="margin:6pt 0 0">Keep this node on USB to a laptop if you want the text dashboard: Serial Monitor at 115200 baud.</p>''')}

{page("Node 3", "Output", "The cup sensor's reading is what stops the pump. The LED shows which pump is running.", f'''
<div class="fig"><p>Node 3 connections</p>{N3}</div>
{note("", "RGB LED", "The LED is common-anode: V is the shared positive. If yours is a bare LED with no small board, put a 220 Ω resistor in line with each of R, G and B.")}
{note("tip", "Cup sensor", "Clip the sensor inside the cup so the water reaches the strips as it fills. The top of the strips is the full line.")}
<h2>What the LED means</h2>{table([("Green", "Ready"), ("Orange", "Coffee pouring"), ("White", "Milk pouring"), ("Yellow", "Cream pouring"), ("Flashing red", "SAFE or DEGRADED: check the dashboard")], ("Color", "Meaning")).replace("<table>", '<table class="plain">')}''')}

{page("Power-up", "Checklist", "Work down the list in order. Join the Wi-Fi the nodes create and open http://barista.io (or http://192.168.4.1).", f'''
{checks(["<b>Each node alone on USB.</b> The OLED lights up on Nodes 2 and 3. Node 1 prints the dashboard address on Serial.",
"<b>All three on.</b> The Live tab shows three nodes ALIVE. The system starts in SAFE: press Acknowledge, or click the joystick.",
"<b>Buzzers.</b> Test tab: Beep Node 1 buzzer, then Beep Node 2 buzzer. Each beeps for one second.",
"<b>LED.</b> Cycle Node 3 LED shows red, then green, then blue.",
"<b>Joystick.</b> The Inputs card shows X and Y near 1900 at rest, moving toward 0 and 4095 when pushed.",
"<b>Water sensors.</b> Note each raw value dry and at the full mark. Put them in <code>LEVEL_RAW_DRY</code> / <code>LEVEL_RAW_FULL</code> on Node 1 and <code>CUP_RAW_DRY</code> / <code>CUP_RAW_FULL</code> on Node 3, then flash again.",
"<b>Pumps, with the pump supply on.</b> Coffee pump 10 mL, then milk, then cream. Each relay clicks and its pump runs briefly.",
"<b>Flow rate.</b> Pour 200 mL into a measuring cup and time it. Put mL divided by seconds into <code>FLOW_ML_PER_S</code> on Node 1, for each pump.",
"<b>Fail-safe.</b> Unplug Node 3 during a pour. The pump stops, both buzzers sound, and the dashboard names the output zone."])}
{note("", "Calibration record", "Write your numbers here so they survive the next flash.")}
{table([("Coffee reservoir", "", "", ""), ("Milk reservoir", "", "", ""), ("Cream reservoir", "", "", ""), ("Cup", "", "", "not used")], ("Sensor", "Raw, dry", "Raw, full", "Pump mL per second")).replace("<table>", '<table class="plain">')}
{note("tip", "Phone tips", "Turn mobile data off so the name barista.io is looked up on the nodes' Wi-Fi, and type the <code>http://</code> part.")}''')}

{page("Troubleshooting", "If something does not work", "Find the symptom on the left. Causes are listed most likely first.", f'''
{table([("Relay clicks, pump does not run", "Diode backwards. Pump on NC instead of NO. Pump supply off or too weak. Pump not under water. Test the pump by touching its wires straight to the supply."),
("Relay clicks on at boot and off when a pour starts", "Active-LOW relay module. Set <code>RELAY_ON</code> to <code>LOW</code> on Node 1."),
("Relay does not click at all", "Relay VCC is not on VIN (5V), or the module will not switch from a 3.3 V signal."),
("Buzzer sounds all the time", "Active-HIGH buzzer module. Set <code>BUZZER_ON</code> to <code>HIGH</code> in that node's sketch."),
("Level stays at 0 % or 100 %", "Sensor on the wrong pin, or the raw dry and full values are not calibrated yet."),
("OLED is blank", "SDA and SCL swapped, or a display that is not at address 0x3C."),
("Menu will not move", "The joystick was held during power-up, or VRx is not reaching GPIO 34. Check Joystick X on the Test tab."),
("LED colors are wrong", "Two of the R, G, B wires are swapped. Run Cycle Node 3 LED to see which."),
("A node shows LOST", "That board is unpowered, or was flashed with a different <code>MESH_SSID</code> or <code>MESH_CHANNEL</code>."),
("barista.io will not load", "Not joined to the nodes' Wi-Fi, mobile data is on, or <code>http://</code> was left off. Use http://192.168.4.1 instead."),
("Stuck in SAFE", "Acknowledge is refused while Node 3 is LOST. Bring Node 3 back, then acknowledge.")], ("Symptom", "Likely cause")).replace("<table>", '<table class="plain">')}''')}
</body></html>'''

# running footers
pages = DOC.split('<section class="page">')
DOC = pages[0] + "".join(f'<section class="page"><div class="foot"><span>MESH BARISTA · WIRING GUIDE</span><span>{i + 2:02d}</span></div>' + p for i, p in enumerate(pages[1:]))
(HERE / "wiring-guide.html").write_text(DOC)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page()
    pg.goto("file://" + str(HERE / "wiring-guide.html"))
    pg.pdf(path=str(HERE.parent / "Mesh-Barista-Wiring-Guide.pdf"), format="Letter", print_background=True,
           margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    b.close()
print("built")
