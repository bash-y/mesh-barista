# Mesh Barista (ENGR 4399, Project 2)

A three-node ESP32 system that pours measured amounts of "coffee", "milk" and "cream" (dyed water).
It is the Project 2 smart water distribution system in a different costume: reservoirs are the source
tanks, the cup is the destination tank.

Team: Sebastian Cadena, Daniel Critchlow Jr

Presentation: [docs/Mesh-Barista-Presentation.pdf](docs/Mesh-Barista-Presentation.pdf)

## Nodes

| Node | Role | Hardware |
|---|---|---|
| 1 | Pump station (spec Node A) | 3 relays + pumps, 3 reservoir water sensors, buzzer |
| 2 | Control center and gateway (spec Node C) | joystick, OLED, buzzer, USB serial dashboard |
| 3 | Output (spec Node B) | cup water sensor, OLED, RGB status LED |

- Radio: ESP-NOW broadcast with a one-hop relay (`barista_mesh.h`). No router, no pairing.
- Messages: JSON with node, zone, seq, uptime, readings and state. Largest (a full order queue) is about 225 bytes (limit 250).
- Cross-node rule: Node 1 stops its pump when Node 3 reports the cup at 90 %.
- Fail-safe: Node 1 goes SAFE on its own (pumps off, buzzer on) when it loses Node 2 or Node 3.
  Leaving SAFE needs an operator acknowledge, and Node 3 must be back. Without Node 2 the system
  then runs DEGRADED from the web dashboard.

## Dashboard

Every node is a Wi-Fi access point with the same name and serves the same page.
Join the Wi-Fi (`MESH_SSID` / `MESH_PASSWORD`) and open **http://barista.io**. The name only works
while you are on that Wi-Fi: each node answers every DNS lookup with its own address, 192.168.4.1.
Type the `http://` part, and turn mobile data off on a phone so the lookup goes to the node.
It keeps working when any one node is off. Node 2 also prints a text dashboard on USB serial (115200).

**Orders.** The dashboard opens on an Order tab: anyone on the Wi-Fi enters a name and picks a drink
(black coffee, latte, coffee & cream, glass of milk). Node 1 keeps the queue (up to 7) and pours a
drink's ingredients one after another. The operator starts each order: a joystick click pours the next
one (Node 2's OLED shows who is next), or open **http://barista.io/#op** for Pour next and Remove
buttons. The page tells each person when their drink is ready. Leave `MESH_PASSWORD` empty (`""`) for
an open network anyone in the room can join.

## Build

1. Arduino IDE with the ESP32 board package. Libraries: ArduinoJson; Adafruit SSD1306 and Adafruit GFX
   for Nodes 2 and 3.
2. Open each `nodeN_*/nodeN_*.ino` and set `MESH_SSID` and `MESH_PASSWORD` (8+ characters), the same
   on all three. The repo keeps placeholders on purpose: do not commit real values.
3. Flash one sketch per board.
4. Calibrate on the dashboard's Test tab: sensor raw values dry and full go into `LEVEL_RAW_*`
   (Node 1) and `CUP_RAW_*` (Node 3); each pump's measured mL per second goes into `FLOW_ML_PER_S`.

**Calibration status (TODO):** the water sensor values in `LEVEL_RAW` (Node 1) and `CUP_RAW` (Node 3)
are mostly **estimates**. Only the reservoirs at the pump's empty point (~1 cm) and the cup dry and at
4.25 cm were measured; the rest follow the usual curve of these strip sensors. The sensors also drift
by 50-100 counts over minutes. Until every point is measured with a ruler, treat the dry-run lock and
the 90 % cup stop as rough backstops: the timed pour is what limits each drink. `FLOW_ML_PER_S` is
also still the default 20 mL/s for every pump. Node 1 prints `levels raw=` and Node 3 `cup raw=` on
serial once a second for calibrating.

To change the page, edit `dashboard_src/dashboard.html` and run `python3 dashboard_src/build_assets.py`.
The script also copies `barista_mesh.h` and `barista_web.h` into each sketch folder.

## Wiring

Step-by-step wiring with connection diagrams, a power-up checklist and troubleshooting are in
[Mesh-Barista-Wiring-Guide.pdf](Mesh-Barista-Wiring-Guide.pdf) (text version: [WIRING.md](WIRING.md)). In short:

**Node 1:** relays IN on GPIO 25 / 26 / 27 (coffee / milk / cream), water sensors on GPIO 32 / 33 / 34,
buzzer on GPIO 13. Pumps run from their own supply through each relay's COM and NO, with the supply
ground tied to ESP32 GND.

**Node 2:** joystick VRx GPIO 32, VRy GPIO 35, SW GPIO 27, powered from 3V3. OLED SDA 21 / SCL 22.
Buzzer GPIO 25.

**Node 3:** cup water sensor GPIO 32. OLED SDA 21 / SCL 22. RGB LED (common anode, V to 3V3)
R 25 / G 26 / B 27.
