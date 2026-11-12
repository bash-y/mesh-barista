# Wiring the Mesh Barista

Build and test one node at a time, with USB unplugged while you move wires.
Pin names are the GPIO numbers; most ESP32 DevKits print them as `D25`, `D32` and so on.

## Rules that apply to every node

- **Signal parts run on 3V3, not 5V.** The water sensors, the joystick and the RGB LED all go on the
  `3V3` pin, even where the part's own pin is labeled `+5V`. Their output follows their supply, and
  more than 3.3 V into an ESP32 input can damage it.
- **Only the relay modules use 5V**, from the `VIN` (or `5V`) pin.
- **All grounds join.** Every part's GND goes to an ESP32 `GND` pin. On Node 1 the pump supply's
  negative goes there too.
- **Pumps never get power from the ESP32.** They run from their own supply, switched by the relays.
- Give each node its own breadboard and run `3V3` and `GND` to the breadboard's power rails first.

## Node 1: pump station

Parts: ESP32, 3 relay modules, 3 pumps, 3 water sensors, 1 buzzer, pump power supply,
3 diodes (1N4007), 3 resistors (10 kΩ, recommended).

### Step 1. Control side (ESP32 to relays, sensors, buzzer)

| Part | Part pin | ESP32 pin |
|---|---|---|
| Relay 1 (coffee) | IN | GPIO 25 |
| Relay 2 (milk) | IN | GPIO 26 |
| Relay 3 (cream) | IN | GPIO 27 |
| All 3 relays | VCC (or DC+) | VIN (5V) |
| All 3 relays | GND (or DC−) | GND |
| Water sensor, coffee reservoir | S | GPIO 32 |
| Water sensor, milk reservoir | S | GPIO 33 |
| Water sensor, cream reservoir | S | GPIO 34 |
| All 3 water sensors | + | 3V3 |
| All 3 water sensors | − | GND |
| Buzzer | I/O (or S) | GPIO 13 |
| Buzzer | VCC | 3V3 |
| Buzzer | GND | GND |

- If a relay module has an H/L jumper, set it to **H** (active-HIGH).
- Pull-down resistors: one 10 kΩ from each of GPIO 25, 26 and 27 to GND. They keep the relays off
  while the ESP32 resets. The system runs without them, but the project spec asks for a defined
  off state, so add them when you have them.

### Step 2. Pump side (one relay, repeated three times)

Each relay has three screw terminals: **COM**, **NO** (normally open) and **NC** (normally closed).
Leave NC empty.

1. Pump supply **+** to the relay's **COM**.
2. The relay's **NO** to the pump's **+** wire (usually red).
3. The pump's **−** wire (usually black) to pump supply **−**.
4. Pump supply **−** to an ESP32 **GND** pin. One wire is enough for all three pumps.
5. A diode across each pump's two wires, with the **striped end on the pump's + wire**.
   A backwards diode shorts the supply the moment the relay closes, and the pump never runs.

```
pump supply +  ──► COM [relay] NO ──► pump + ──(pump)── pump − ──► pump supply −
                                         │                 │              │
                                         └──|◄── diode ────┘              └──► ESP32 GND
                                        (stripe on the + side)
```

Using NO means a pump can only run while the ESP32 is actively holding its relay on.

### Step 3. Water and tubing

- Put each pump at the bottom of its reservoir. Submersible pumps must be under water to pump.
- Clip each water sensor inside its reservoir with the bare strips pointing down. Keep the
  electronics at the top of the sensor dry.
- Run the three outlet tubes to the cup on Node 3.

## Node 2: control center

Parts: ESP32, joystick, OLED (4-pin I2C), buzzer.

| Part | Part pin | ESP32 pin |
|---|---|---|
| Joystick | VRx | GPIO 34 |
| Joystick | VRy | GPIO 35 |
| Joystick | SW | GPIO 27 |
| Joystick | +5V | **3V3** |
| Joystick | GND | GND |
| OLED | SDA | GPIO 21 |
| OLED | SCL (or SCK) | GPIO 22 |
| OLED | VCC | 3V3 |
| OLED | GND | GND |
| Buzzer | I/O (or S) | GPIO 25 |
| Buzzer | VCC | 3V3 |
| Buzzer | GND | GND |

- Leave the joystick alone while this node powers up. It measures the stick's resting position then.
- Keep this node on USB to a laptop if you want the text dashboard (Serial Monitor, 115200 baud).

## Node 3: output

Parts: ESP32, 1 water sensor, OLED (4-pin I2C), RGB LED (4-pin, marked V G B R).

| Part | Part pin | ESP32 pin |
|---|---|---|
| Water sensor (cup) | S | GPIO 32 |
| Water sensor | + | 3V3 |
| Water sensor | − | GND |
| OLED | SDA | GPIO 21 |
| OLED | SCL (or SCK) | GPIO 22 |
| OLED | VCC | 3V3 |
| OLED | GND | GND |
| RGB LED | V | 3V3 |
| RGB LED | R | GPIO 25 |
| RGB LED | G | GPIO 26 |
| RGB LED | B | GPIO 27 |

- The LED is common-anode: V is the shared positive. If yours is a bare LED with no small board,
  put a 220 Ω resistor in line with each of R, G and B.
- Clip the water sensor inside the cup so the water reaches the strips as it fills. The top of the
  strips is the "full" line.

## Power-up checks

Do these in order. Each one uses the dashboard: join the Wi-Fi the nodes create and open
`http://192.168.4.1`.

1. **Each node alone on USB.** The OLED lights up on Nodes 2 and 3. Node 1 prints its address on Serial.
2. **All three on.** The Live tab shows three nodes ALIVE. The system starts in SAFE; press
   Acknowledge (or click the joystick).
3. **Buzzers.** Test tab, "Beep Node 1 buzzer" and "Beep Node 2 buzzer". If a buzzer sounds all the
   time and goes quiet during the test, change `BUZZER_ON` to `HIGH` in that node's sketch.
4. **LED.** "Cycle Node 3 LED" shows red, then green, then blue. A wrong order means two of the
   R, G, B wires are swapped.
5. **Joystick.** The Inputs card shows Joystick X and Y near 1900 at rest, moving toward 0 and 4095
   when pushed. A value stuck near 0 or 4095 means that axis wire, 3V3 or GND is loose.
6. **Water sensors.** The Inputs card shows each raw value. Note it dry and at the full mark, then put
   the numbers in `LEVEL_RAW_DRY` / `LEVEL_RAW_FULL` (Node 1) and `CUP_RAW_DRY` / `CUP_RAW_FULL`
   (Node 3) and flash again.
7. **Pumps, with the pump supply on.** "Coffee pump, 10 mL", then milk, then cream. Each relay
   should click and its pump should run briefly.
8. **Flow rate.** Pour 200 mL of one ingredient into a measuring cup and time it. Put mL divided by
   seconds into `FLOW_ML_PER_S` on Node 1. Repeat for each pump.

## If something does not work

| Symptom | Likely cause |
|---|---|
| Relay clicks, pump does not run | Diode backwards; pump on NC instead of NO; pump supply off or too weak; pump not under water. Test the pump by touching its wires straight to the supply. |
| Relay clicks on at boot and off when a pour starts | Active-LOW relay module. Set `RELAY_ON` to `LOW` on Node 1. |
| Relay does not click at all | Relay VCC not on VIN (5V), or a 5V module that will not switch from a 3.3 V signal. |
| Level stays at 0 % or 100 % | Sensor on the wrong pin, or `*_RAW_DRY` / `*_RAW_FULL` not calibrated yet. |
| OLED blank | SDA and SCL swapped, or a screen that is not at address 0x3C. |
| Menu will not move | Joystick was held during power-up, or VRx is not reaching GPIO 34. |
| A node shows LOST | That board is unpowered, or flashed with a different `MESH_SSID` or `MESH_CHANNEL`. |
