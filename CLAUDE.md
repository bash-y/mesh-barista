# Mesh Barista (ENGR 4399 Project 2)

Three ESP32 nodes pour measured coffee/milk/cream (dyed water) over an ESP-NOW broadcast mesh.
Team: Sebastian "Bash" Cadena, Daniel Critchlow Jr. Not GRIM-01RE / GRIM-02RE (different project; never mention).

## Layout
- node1_pump_station/ pumps + 3 reservoir level sensors + buzzer
- node2_control_center/ joystick + OLED + buzzer (the user interface)
- node3_output/ cup level sensor + OLED + RGB status LED
- Each node folder: <node>.ino, barista_mesh.h, barista_web.h, dashboard_html.h. The mesh/web headers and dashboard_html.h are copies, generated from dashboard_src/ (`python3 dashboard_src/build_assets.py`). Edit dashboard_src/, never the copies.
- harness/ host-side tests: `harness/run.sh` (firmware sim in C++ with Arduino stubs, then Playwright browser test of the dashboard). Both must pass before any push.
- docs/ wiring guide + presentation sources; WIRING.md wiring instructions.
- (3D parts live outside the repo for now: STL generators in /home/claude/holder, copy them into stl/ if wanted.)

## Design rules
- ESP-NOW broadcast, own one-hop relay (seq dedupe, hop count), 250-byte frame limit (largest ~175 B). Callback signature differs for ESP32 core 2.x vs 3.x.
- Every node is a Wi-Fi AP, same SSID/password, 192.168.4.1, DNS wildcard so http://barista.io works. Endpoints /, /data, /cmd. Dashboard works from any node, so it survives Node 2 being off.
- States NORMAL / DEGRADED / SAFE. Boot in SAFE. Lock an ingredient <10%, unlock >20%. Cup full 90%. Cup data stale after 1.5 s, node LOST after 3 s. ACK needs Node 3 alive; Node 2 optional (gives DEGRADED).
- Pins: Node1 relays 25/26/27 (coffee/milk/cream), sensors 32/33/34, buzzer 13. Node2 joystick X34 Y35 SW27, OLED 21/22, buzzer 25. Node3 cup sensor 32, OLED 21/22, RGB 25/26/27 (common anode, LOW = on). Analog only on ADC1 (32-39).
- Relays active-HIGH; avoid strapping pins 0/2/5/12/15. Joystick is calibrated at boot (resting value), thresholds are relative.
- MESH_SSID / MESH_PASSWORD are CHANGE_ME placeholders.

## Not yet verified on hardware
Nothing has been compiled for a real ESP32. Pumps did not run in the first bench test (suspect pump circuit: diode direction, COM/NO, supply). Calibrate LEVEL_RAW_*, CUP_RAW_*, FLOW_ML_PER_S. Wokwi project for the PR2 deliverable is stale (old one-pump design). Deck Results slide has placeholders.

## Workflow
Small diffs. Run harness/run.sh after any firmware or dashboard change. After editing dashboard_src/, rebuild assets and rerun. Commit with clear messages; don't push without being asked.
