# Mesh Barista: agent handoff

Status as of 2026-11-12 (commit `3d98b44`), for whoever picks this up next, human or agent.
Read `README.md` first for what the system is. This file is what is **not done yet**, how to work on the
hardware safely, and the traps we already hit.

The work itself is tracked as GitHub issues on the project board. Before creating or estimating an issue,
read `docs/AGILE.md`: it has the issue conventions the UIW-PMD dashboard reads (type, `Parent: #N`,
`Story points: N`, `Blocked by #N`) and the **story points guide** (1, 2, 3, 5, 8, 13 by how much is known,
dependencies and effort; 8 should be split, 13 must be).

## Current state in one paragraph

All three nodes run the latest firmware: ESP-NOW mesh, a web dashboard on every node, an order queue
for a live class demo (anyone on the Wi-Fi orders from their phone), a watchdog on Node 1, and pour
music on the passive buzzers. The boards are flashed with an **open** Wi-Fi network called `Bashy`
(`MESH_PASSWORD ""`) so the audience can join; the repo keeps the `CHANGE_ME` placeholders on purpose.
The big remaining gaps are **sensor calibration** (mostly estimates), **pump flow rates** (defaults),
the **cream pump's electrical noise**, and **no hardware test of the order queue** yet.

## To-do list, most important first

### Before the live demo

1. **Dry run the order queue on real hardware.** Never done. Join `Bashy` from 2-3 phones, open
   `http://barista.io`, place orders, pour them with joystick clicks (or `http://barista.io/#op`).
   Check: a latte pours coffee then milk with one continuous tune, the "ready" toast appears on the
   orderer's phone, Node 2/3 OLEDs show the name. Pump supply can stay off (relays still click).
2. **Measure each pump's flow rate.** `FLOW_ML_PER_S` in `node1_pump_station.ino` is still the default
   `20.0` for all three, so every timed pour is a guess. Run each pump 10 s into a measuring cup, mL / 10.
   Then measure the error on a 60 mL pour. Slide 6 currently shows the 20 mL/s default, labelled as an
   estimate: set `FLOW_ML_S` at the top of `docs/build_presentation.py` to the measured rate, reword the
   two hardware stats in `STATS` to say measured (adding the pour error), and rebuild (see "Building the docs").
3. **Fix the cream pump's electrical noise.** Starting the cream pump froze Node 1 twice (once with the
   relay closed). The watchdog now resets Node 1 into SAFE with all pumps off, so it is safe, but it
   will interrupt a demo. Fix: flyback diode across the cream pump (1N4007, stripe to +), pump supply
   ground tied to ESP32 GND with a short wire, 0.1 uF across the motor, wires away from the ESP32.
   Swap pumps to see if it follows the pump or the relay (GPIO 27). After a reset, Node 1's event log
   says why: "restarted by the watchdog" vs "restarted by a brownout".
4. **Fill the reservoirs above ~1.8 cm.** Below 20 % (of the usable depth) the pumps stay locked.
5. ~~Hide the Test and System tabs from the audience~~ **Done.** Without `#op` the page shows only the
   Order and Live tabs and no Acknowledge button (anyone can still press Stop pump). This only hides
   the controls: `/cmd` still accepts any command, so it is not security.
6. **Listen to the sounds once.** Written and flashed but never confirmed by ear: Node 2 boot chime,
   Node 2 jazz melody + Node 1 coffee-machine gurgle while pouring, "drink ready" phrase, and the
   2.7 kHz alarm (the old alarm was silent on passive buzzers). Tuning knobs are in
   `dashboard_src/barista_music.h` (`gurgleNow()`, `TUNE_*`). `POUR_SOUND` in Node 1 switches the
   gurgle to a walking bass line or off.

### Calibration (needs a ruler; "later" is fine, but the safety stops are rough until then)

7. **Measure the water sensors properly.** Values are marked `TODO(calibration)` in both sketches.
   Raw values: dashboard Test tab, or serial (`levels raw=` on Node 1, `cup raw=` on Node 3, once a second).
   - Reservoirs (`LEVEL_RAW` in Node 1, one row each): sensor stands on the bottom, strips reach 5.1 cm.
     0 % = the level a pump stops pulling (~1.0 cm), then 2.5, 3.8, 5.1 cm. Only the 0 % column is real.
   - Cup (`CUP_RAW` in Node 3): strips' top is 3 cm below the lip and is the "full" line (100 %).
     Points: dry, 3.4, 4.6, 5.9, 7.2, 8.4 cm from the inside bottom. Measured so far: dry = 138,
     4.25 cm = 1054. The rest are estimates.
   - Each row must strictly increase. `CUP_PCT` / `LEVEL_PCT` hold the matching percentages.
8. **Stop the sensor drift first (recommended).** Readings drift 50-100 counts over minutes (the milk
   sensor went 1266 -> 1168 at a constant level; the cup read lower with more water). That is as big as
   the whole useful range near full, so the 90 % cup stop and 10 % dry-run lock are only rough backstops.
   Likely cause: the strips corrode/polarise because they are powered all the time. Fix: power each
   sensor's + pin from a spare GPIO, switch it on ~10 ms before reading, off after. Needs free pins and a
   wiring change on Nodes 1 and 3, then recalibrate.
9. **Check the dry-run lock height.** The lock trips at 10 % of the usable depth (~1.4 cm). If a pump's
   intake sits higher, raise `LEVEL_LOCK_PCT` / `LEVEL_UNLOCK_PCT`.

### Docs

10. **Wiring guide PDF is partly out of date** (`docs/build_wiring_pdf.py`, then rebuild):
    - Power-up check "Water sensors" (around line 184) still names `LEVEL_RAW_DRY` / `LEVEL_RAW_FULL` /
      `CUP_RAW_DRY` / `CUP_RAW_FULL`. Now `LEVEL_RAW` and `CUP_RAW` multi-point tables (see `WIRING.md` step 6).
    - Cup sensor note (around line 175): add "top of the strips 3 cm below the lip".
    - Troubleshooting "Buzzer sounds all the time" assumes an active buzzer. The buzzers are passive and
      are driven with a tone now; replace with "No sound: check I/O on the right GPIO; a passive buzzer
      needs a tone, not HIGH/LOW".
    - It already shows VRx on GPIO 32.
11. **README hardware line** still says Node 1/2 "buzzer" without noting passive; fine, but mention it if
    you touch that section.

### Known code weaknesses (not urgent, worth knowing)

12. **Mesh duplicate filter is weak.** `barista_mesh.h` drops a message only if its `seq` equals the
    *last* seq seen from that node, so a relayed copy arriving after a newer message is processed twice
    (we saw doubled "pour refused: already pouring"). Orders (random key `k`) and `next` / `drop` (order
    id) are made safe against this. **`deaf` is not**: a doubled `deaf` toggles twice and does nothing.
    Proper fix: keep a small window of recent seqs per node instead of one.
13. **Web server can block a node up to 5 s** (Arduino `WebServer` waits on a slow phone). Node 1's
    watchdog is 3 s, so a phone with bad Wi-Fi could reset Node 1 into SAFE (logged as a watchdog
    restart). If that shows up, raise `WATCHDOG_MS` to ~6000 or move to an async web server.
14. **The order queue lives in Node 1's RAM.** A Node 1 reset (watchdog, unplug) empties it; people
    re-order. Max 7 orders and 10-character names, so the queue message fits one 250-byte ESP-NOW frame
    (worst case 225 bytes). The drink menu is defined twice and must match: `DRINK_NAME` / `DRINK_ML` in
    `dashboard_src/barista_web.h` and `DRINKS` in `dashboard_src/dashboard.html`.

## Presentation feedback (2026-11-12): where to take it next

Dr. Okan liked the project. These are his points from the class presentation, as directions for the
next version rather than demo fixes. Each one builds on the gaps above.

15. **Measurement accuracy is the main thing to develop.** Today a pour is a timed pump burst at an
    estimated rate (to-do 2) and the level sensors are rough backstops (to-dos 7-8), so we cannot yet
    say how many mL actually land in the cup. The next version needs a measured accuracy figure (for
    example, error on repeated 60 mL pours) and a way to improve it.
16. **Flow-rate ("CFM") control for different liquids.** Liquids such as milk, cream, syrups and
    alcohol have different viscosities, so one pump moves them at different rates. Look into
    calibrating flow per liquid, or measuring flow while pouring (a flow sensor) and closing the loop,
    instead of one fixed `FLOW_ML_PER_S` per pump. Note: CFM (cubic feet per minute) is a gas unit;
    for liquids we would report mL/s.
17. **Applications that need accurate doses:** bartending (exact pours per drink) and pharma, for
    example measuring antibiotics and similar doses. These raise the accuracy bar a lot, and pharma
    would also need traceability and materials that are safe for medicine. Keep them in mind when
    choosing what accuracy to aim for.
18. **Watertight, safe materials.** He was concerned about which materials touch the liquid and
    whether the build is watertight: tubing, fittings, containers and sensor mounting. The electronics
    sit next to open water today. Choose food-safe (and, for pharma, medical-grade) parts, seal the
    joints, and keep the electronics separate from the wet side.
19. **Pump and container selection.** Choose pumps and reservoirs for the job, not just what was on
    hand: how accurate and repeatable each pump type is at small volumes (for example, a peristaltic
    pump keeps the liquid inside the tube, which also helps with materials and cleaning), what liquids
    it can handle, and container material, shape and size.
20. **If we move to pressure-plate (weight) sensors, have an accuracy plan.** This is the "load cell
    under the cup" idea from the Lessons slide. Before committing, work out how to handle calibration
    with known weights, tare (an empty cup), drift with temperature and time, vibration while the
    pump runs, liquid density (weight to mL differs per liquid), and the resolution needed for small
    doses.
21. **Make it an accessory, not a replacement.** Position Mesh Barista as an add-on to the machines
    people already own, not a coffee machine that replaces them. That means designing adapters and
    couplings for things like Nespresso and Keurig machines, for example adding milk or cream to the
    cup a machine has just made.

## How to work on the hardware

**Board:** generic ESP32 Dev Module, FQBN `esp32:esp32:esp32` (core `esp32:esp32` 3.3.x).
Libraries: ArduinoJson 7, Adafruit SSD1306 + GFX (Nodes 2 and 3).

**Shared files:** never edit `barista_mesh.h`, `barista_web.h`, `barista_music.h` or `dashboard_html.h`
inside a node folder. Edit the masters in `dashboard_src/` and run `python3 dashboard_src/build_assets.py`,
which copies them into all three sketch folders and regenerates the gzipped page.

**Flashing without committing credentials.** Copy the sketch to a scratch folder, set the Wi-Fi there,
compile and upload from the copy. The repo must keep `CHANGE_ME_SSID` / `CHANGE_ME_PASSWORD`.

```sh
S=/tmp/barista-build; n=node1_pump_station; port=/dev/cu.usbserial-4
mkdir -p "$S" && rm -rf "${S:?}/${n:?}" && cp -R "$n" "$S/"
sed -i '' 's/"CHANGE_ME_SSID"/"Bashy"/; s/"CHANGE_ME_PASSWORD"/""/' "$S/$n/$n.ino"
arduino-cli compile --fqbn esp32:esp32:esp32 --upload -p "$port" "$S/$n"
```

Ports on the development Mac last time: Node 1 `/dev/cu.usbserial-4`, Node 2 `/dev/cu.usbserial-3`,
Node 3 `/dev/cu.usbserial-0001`. They can change on replug: check with `ls /dev/cu.usbserial-*` and
confirm by reading the boot line (`ESP-NOW up on channel 1, node N`).

**Every flash or reset of Node 1 puts it in SAFE.** Click the joystick (or Acknowledge on the
dashboard) once to leave SAFE.

## Traps we already fell into

- **Opening a serial port resets the board on this Mac**, even with DTR/RTS set false. Reading Node 1
  or 3 can briefly drop them; reading Node 1 resets it into SAFE and **empties the order queue**.
- **The USB serial driver sometimes repeats the last line thousands of times** (looks like a board
  spamming one message at an impossible rate). It is the driver, not the firmware. When reading with
  pyserial, discard any `read()` that returns more than ~2000 bytes and keep reading.
- **A port can get stuck** (`termios.error: (22, 'Invalid argument')`). Unplug and replug the board.
- **GPIO 34 on Node 2's board reads ~0 V** even with nothing attached; that is why the joystick X
  moved to GPIO 32. Don't move it back.
- **Building the PDFs needs Python 3.12+ with Playwright**, and the system `python3` is 3.9. Make a venv:
  `/opt/homebrew/bin/python3.12 -m venv /tmp/pyvenv && /tmp/pyvenv/bin/pip install playwright qrcode`.
- **Wi-Fi password must be 0 or 8+ characters.** 1-7 characters and the access point never starts
  (ESP-NOW still works, the dashboard doesn't).

## Building the docs

```sh
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" /tmp/pyvenv/bin/python docs/build_wiring_pdf.py
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" /tmp/pyvenv/bin/python docs/build_presentation.py
```

The presentation loads its fonts from Google Fonts, so it needs internet. Its placeholders and the
QR code's Wi-Fi name are constants at the top of `docs/build_presentation.py`.

## Hardware facts worth keeping

- Cup: 4.5" (11.4 cm) tall. Sensor strips 5.07 cm (68.5 mm board minus 17.8 mm connector).
- Buzzers on Nodes 1 and 2 are **passive** (need a tone). Alarm tone `ALARM_HZ` = 2700.
- Pumps can't pull below ~1.0 cm of liquid in their reservoirs.
- Node 3's cup reading drives the cross-node stop; Node 1 needs a fresh cup reading (< 1.5 s) to pour.
