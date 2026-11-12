// Mesh Barista  PR2  -  NODE 2: CONTROL CENTER + GATEWAY  (spec Node C)
//
// Owns:    joystick (menu), OLED, buzzer, and the dashboard on USB serial (115200 baud).
// Joystick: left/right = coffee/milk/cream, up/down = mL, click = pour. In SAFE, click = operator ACK.
//           With orders waiting in the queue, click = pour the next order instead.
// Dashboard (reprinted every second): each node ALIVE/LOST + time since heartbeat, sensor values,
//          pump state, system state, affected zone, live mesh topology, and a timestamped event log.
// Radio:   ESP-NOW (barista_mesh.h). No router, no pairing: broadcast, with a one-hop relay.
// Web:     the same dashboard as a web page (barista_web.h). Nodes 1 and 3 host it too, so it
//          stays reachable when this node is off.
//
// Libraries: ArduinoJson, Adafruit SSD1306, Adafruit GFX. ESP-NOW and WebServer come with the board package.
// Files:     barista_mesh.h, barista_web.h and dashboard_html.h must sit in this sketch folder.

#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Placeholders: set the same values on all 3 nodes locally. Never share the real ones (report, Wokwi, git).
#define MESH_SSID     "CHANGE_ME_SSID"
#define MESH_PASSWORD "CHANGE_ME_PASSWORD"

const int   NODE_ID = 2;
const char* ZONE    = "control";
const char* ING[3]  = {"coffee", "milk", "cream"};

// ---------- pins ----------
const int JOY_X_PIN  = 32;   // ADC1 only: ADC2 reads garbage while the mesh radio is on
const int JOY_Y_PIN  = 35;
const int JOY_SW_PIN = 27;   // LOW when pressed
const int BUZZER_PIN = 25;
const int BUZZER_ON  = LOW;  // idle level is the opposite, so no current flows while silent
const uint32_t ALARM_HZ = 2700;  // passive buzzer: alarm and test beeps are a tone at this pitch
const bool MUSIC_ON = true;      // melody while a pump runs, a "drink ready" phrase after, boot chime

// ---------- tuning ----------
const int JOY_PUSH = 700, JOY_REST = 300;   // a push = this far from the resting value; back within REST re-arms
int joyCX = 1900, joyCY = 1900;             // resting values, measured at boot (don't touch the stick then)
const int ML_STEP = 10, ML_MIN = 10, ML_MAX = 240;
const unsigned long HEARTBEAT_MS = 1000;
const unsigned long LOST_MS      = 3000;  // 3 missed heartbeats, direct or relayed

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;

struct Peer { int id; const char* zone; unsigned long lastSeen; bool alive; };
Peer  peers[] = {{1, "pump station", 0, false}, {3, "output", 0, false}};
Peer& node1   = peers[0];
Peer& node3   = peers[1];

// latest data from the other nodes
int    lvl[3] = {-1, -1, -1};
int    pump   = 0;                 // 0 none, 1 coffee, 2 milk, 3 cream
String n1State = "?", n1Why = "", n1Sees = "";
int    cup = -1;
String n3State = "?", n3Sees = "";

String sysState = "", affected = "";
int    sel = 0, ml = 60;           // menu selection
int    joyX = 0, joyY = 0;
unsigned long buzzTestUntil = 0;   // dashboard buzzer test
uint32_t seq = 0;
// the order queue, as Node 1 last broadcast it
int    qLen = 0, qHeadId = -1, qHeadDrink = 0, n1Ord = -1, curDrink = 0;
String qHeadName = "", curName = "";

#include "barista_mesh.h"
#include "barista_web.h"
#include "barista_music.h"

void handleOrder(JsonDocument& doc) {}  // Node 1 keeps the queue

// ---------- messaging ----------
void addHeader(JsonDocument& doc) {
  doc["node"] = NODE_ID;
  doc["zone"] = ZONE;
  doc["seq"]  = seq++;
  doc["up"]   = millis();
}

void sendDoc(JsonDocument& doc) { meshSend(doc); }

// Events go to this node's log (serial + web dashboard) and to the mesh for the other nodes' logs.
void logEvent(const String& msg) {
  webLog(String("Node ") + NODE_ID + ": " + msg);
  DynamicJsonDocument doc(256);
  addHeader(doc);
  doc["evt"] = msg;
  sendDoc(doc);
}

void sendStatus() {
  DynamicJsonDocument doc(1024);
  addHeader(doc);
  JsonArray joy = doc.createNestedArray("joy");
  joy.add(joyX);
  joy.add(joyY);
  doc["sel"]   = sel;   // the menu selection, so the dashboard can show the joystick working
  doc["ml"]    = ml;
  doc["state"] = sysState;
  JsonArray alive = doc.createNestedArray("alive");  // link status as this node sees it
  for (auto& p : peers) if (p.alive) alive.add(p.id);
  doc["ip"] = WiFi.softAPIP().toString();            // where this node serves the dashboard
  meshSend(doc);
  String out;
  serializeJson(doc, out);
  webStore(NODE_ID, out);
}

// ---------- state ----------
void checkPeers() {
  for (auto& p : peers) {
    bool alive = p.lastSeen && millis() - p.lastSeen < LOST_MS;
    if (alive == p.alive) continue;
    p.alive = alive;
    logEvent(String("Node ") + p.id + " (" + p.zone + ") " + (alive ? "ALIVE" : "LOST"));
  }
}

void evalSystem() {
  String s, z;
  if (!node1.alive)               { s = "SAFE"; z = node1.lastSeen ? "pump station (Node 1) LOST" : "waiting for Node 1"; }
  else if (!node3.alive)          { s = "SAFE"; z = node3.lastSeen ? "output (Node 3) LOST" : "waiting for Node 3"; }
  else if (n1State == "SAFE")     { s = "SAFE"; z = "pump station: " + n1Why; }
  else if (n1State == "DEGRADED") { s = "DEGRADED"; z = "pump station: reservoir low"; }
  else                            { s = "NORMAL"; z = "-"; }
  if (s == sysState && z == affected) return;
  sysState = s;
  affected = z;
  logEvent("SYSTEM " + s + "  zone: " + z);
}

void handleCmd(const char* cmd, int to, int ing, float ml) {
  if (!strcmp(cmd, "buzz") && to == NODE_ID) buzzTestUntil = millis() + 1000;
  // Demo aid: make node `to` act as if node `ing` were out of range, to show the relay path.
  else if (!strcmp(cmd, "deaf") && to == NODE_ID && ing >= 1 && ing <= 3) {
    meshDeaf[ing] = !meshDeaf[ing];
    logEvent(String("Node ") + ing + (meshDeaf[ing] ? " treated as out of range" : " back in range"));
  }
}

void onMeshMessage(const String& raw, JsonDocument& doc, int src, int hop, int via) {
  Peer* p = src == 1 ? &node1 : &node3;
  p->lastSeen = millis();
  checkPeers();
  if (!doc["evt"].isNull()) webLog(String("Node ") + src + ": " + doc["evt"].as<const char*>());
  if (!doc["cmd"].isNull()) handleCmd(doc["cmd"] | "", doc["to"] | 0, doc["ing"] | -1, doc["ml"] | 0.0f);
  if (src == 1 && !doc["queue"].isNull()) {  // the order queue
    webQueueStore(raw);
    JsonArrayConst q = doc["queue"].as<JsonArrayConst>();
    qLen = q.size();
    qHeadId    = qLen ? q[0][0].as<int>() : -1;
    qHeadName  = qLen ? q[0][1].as<const char*>() : "";
    qHeadDrink = qLen ? q[0][2].as<int>() : 0;
    curName    = doc["cur"].isNull() ? "" : doc["cur"][1].as<const char*>();
    curDrink   = doc["cur"][2] | 0;
    return;
  }
  if (doc["state"].isNull()) return;  // an event or a command, not a status message
  webStore(src, raw);

  String sees;
  for (JsonVariantConst a : doc["alive"].as<JsonArrayConst>()) sees += String(a.as<int>()) + " ";
  if (src == 1) {
    for (int i = 0; i < 3; i++) lvl[i] = doc["lvl"][i] | -1;
    pump    = doc["pump"] | 0;
    n1Ord   = doc["ord"] | -1;  // the order being poured, -1 = none
    n1State = doc["state"].as<const char*>();
    n1Why   = doc["why"] | "";
    n1Sees  = sees;
  } else {
    cup     = doc["cup"] | -1;
    n3State = doc["state"].as<const char*>();
    n3Sees  = sees;
  }
}

// ---------- joystick ----------
void onClick() {
  if (!node1.alive) { logEvent("click ignored: Node 1 not connected"); return; }
  DynamicJsonDocument doc(256);
  addHeader(doc);
  if (n1State == "SAFE") {
    doc["cmd"] = "ack";
    logEvent("operator ACK sent");
  } else if (n1Ord >= 0) {
    logEvent("click ignored: an order is pouring");
    return;
  } else if (qLen > 0) {
    doc["cmd"] = "next";
    doc["ing"] = qHeadId;  // name the order, so a duplicate copy of this command does nothing
    logEvent(String("pour next order: #") + qHeadId + " " + qHeadName);
  } else {
    doc["cmd"] = "pour";
    doc["ing"] = sel;
    doc["ml"]  = ml;
    logEvent(String("pour requested: ") + ING[sel] + " " + ml + " mL");
  }
  sendDoc(doc);
}

void readJoystick() {
  static bool armed = true, lastBtn = HIGH;
  static unsigned long lastPress = 0;
  joyX = analogRead(JOY_X_PIN);
  joyY = analogRead(JOY_Y_PIN);
  int dx = joyX - joyCX, dy = joyY - joyCY;
  if (abs(dx) < JOY_REST && abs(dy) < JOY_REST) armed = true;  // one step per push: back to rest before the next
  else if (armed) {
    armed = false;
    if      (dx < -JOY_PUSH) sel = (sel + 2) % 3;
    else if (dx >  JOY_PUSH) sel = (sel + 1) % 3;
    else if (dy < -JOY_PUSH) ml = min(ML_MAX, ml + ML_STEP);  // swap + and - if up/down feels reversed
    else if (dy >  JOY_PUSH) ml = max(ML_MIN, ml - ML_STEP);
    else armed = true;         // not pushed far enough yet
  }
  bool btn = digitalRead(JOY_SW_PIN);
  if (btn == LOW && lastBtn == HIGH && millis() - lastPress > 300) { lastPress = millis(); onClick(); }
  lastBtn = btn;
}

// ---------- outputs ----------
String ago(unsigned long lastSeen) {
  return lastSeen ? String((millis() - lastSeen) / 1000.0, 1) + "s" : String("never");
}

void printDashboard() {
  Serial.println();
  Serial.printf("=============== MESH BARISTA DASHBOARD   t=%.1fs ===============\n", millis() / 1000.0);
  Serial.printf("SYSTEM: %s     AFFECTED ZONE: %s\n", sysState.c_str(), affected.c_str());
  Serial.printf("Node 1  pump station  %-5s  last hb %-6s  coffee %d%%  milk %d%%  cream %d%%  pump: %s  state: %s  sees: %s%s\n",
                node1.alive ? "ALIVE" : "LOST", ago(node1.lastSeen).c_str(), lvl[0], lvl[1], lvl[2],
                pump ? ING[pump - 1] : "OFF", n1State.c_str(), n1Sees.c_str(), node1.alive ? "" : " (stale)");
  Serial.printf("Node 2  control (me)  ALIVE  menu: %s %d mL  joystick x=%d y=%d\n", ING[sel], ml, joyX, joyY);
  Serial.printf("Node 3  output        %-5s  last hb %-6s  cup %d%%  state: %s  sees: %s%s\n",
                node3.alive ? "ALIVE" : "LOST", ago(node3.lastSeen).c_str(), cup,
                n3State.c_str(), n3Sees.c_str(), node3.alive ? "" : " (stale)");
  Serial.printf("ORDERS  %d waiting%s%s   pouring: %s\n", qLen, qLen ? ", next: " : "", qLen ? qHeadName.c_str() : "",
                n1Ord >= 0 ? (curName + " - " + DRINK_NAME[curDrink]).c_str() : "none");

  Serial.println("LINKS (as Node 2 hears them):");
  for (int n = 1; n <= 3; n++) {
    if (n == NODE_ID) continue;
    if (meshDirect(n))   Serial.printf("  Node %d: direct\n", n);
    else if (meshVia(n)) Serial.printf("  Node %d: relayed by Node %d (multi-hop)\n", n, meshVia(n));
    else                 Serial.printf("  Node %d: no path\n", n);
  }
  Serial.printf("  radio: %lu sent, %lu relayed, %lu dropped\n", meshSent, meshRelayed, meshDropped);

  Serial.println("EVENTS:");
  for (int i = 0; i < WEB_LOG_N; i++) {
    WebEvent& e = webEvents[(webLogHead + i) % WEB_LOG_N];
    if (e.m.length()) Serial.printf("  %8.1fs  %s\n", e.t / 1000.0, e.m.c_str());
  }
}

void updateOled() {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("Node 2  ");
  oled.println(WEB_HOST);  // the dashboard address
  bool pouringOrder = node1.alive && n1Ord >= 0, waiting = node1.alive && qLen > 0;
  if (pouringOrder || waiting) {  // the queue: whose drink is pouring, or who is next
    if (pouringOrder) oled.println("Pouring for:");
    else { oled.print("Next of "); oled.print(qLen); oled.println(" waiting:"); }
    oled.setTextSize(2);
    oled.println(pouringOrder ? curName : qHeadName);
    oled.setTextSize(1);
    oled.println(DRINK_NAME[pouringOrder ? curDrink : qHeadDrink]);
  } else {                        // no orders: the joystick menu
    oled.setTextSize(2);
    oled.print(">");
    oled.println(ING[sel]);
    oled.print(" ");
    oled.print(ml);
    oled.println(" mL");
    oled.setTextSize(1);
  }
  oled.print("System: ");
  oled.println(sysState);
  oled.print("Pump:   ");
  oled.println(pump ? ING[pump - 1] : "off");
  oled.println(sysState == "SAFE" ? "Click = ACK" : pouringOrder ? "Pouring..." : waiting ? "Click = POUR NEXT" : "Click = POUR");
  oled.display();
}

void setup() {
  buzzerOff();
  pinMode(JOY_SW_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) Serial.println("OLED not found at 0x3C - running without it");

  meshBegin(MESH_SSID, MESH_PASSWORD);
  webBegin();
  logEvent("boot");

  // Joysticks rarely rest at exactly mid-scale, so measure where this one rests.
  long sx = 0, sy = 0;
  for (int i = 0; i < 16; i++) { sx += analogRead(JOY_X_PIN); sy += analogRead(JOY_Y_PIN); }
  joyCX = sx / 16;
  joyCY = sy / 16;
  // A resting value at either end of the scale means that axis is not really connected.
  if (joyCX < 600 || joyCX > 3500) logEvent(String("joystick X rests at ") + joyCX + ": check the VRx wire, 3V3 and GND");
  if (joyCY < 600 || joyCY > 3500) logEvent(String("joystick Y rests at ") + joyCY + ": check the VRy wire, 3V3 and GND");
  if (MUSIC_ON) musicPlay(TUNE(TUNE_BOOT), false, millis());
}

void loop() {
  static unsigned long lastJoy = 0, lastBeat = 0, lastDraw = 0;
  meshLoop();
  webLoop();
  unsigned long now = millis();
  checkPeers();
  evalSystem();
  if (now - lastJoy >= 20) { lastJoy = now; readJoystick(); }
  if (now - lastBeat >= HEARTBEAT_MS) { lastBeat = now; sendStatus(); printDashboard(); }
  if (now - lastDraw >= 250) { lastDraw = now; updateOled(); }
  // Alarm in SAFE once both nodes have been seen. A fresh boot waiting for its first ACK is not a fault.
  bool alarm = sysState == "SAFE" && node1.lastSeen && node3.lastSeen && !(node1.alive && node3.alive && n1Why == "boot");
  bool beep  = now < buzzTestUntil || (alarm && (now / 300) % 2);
  // Music follows Node 1's pump: the melody while it runs (Node 1 plays the bass), then "drink ready".
  static int lastPump = 0;
  int p = node1.alive && (pump || n1Ord >= 0);  // a whole order, not each ingredient; a lost Node 1 is stale
  if (MUSIC_ON && p && !lastPump) musicPlay(TUNE(TUNE_MELODY), true, now);
  if (!p && lastPump) { if (MUSIC_ON && node1.alive) musicPlay(TUNE(TUNE_READY), false, now); else musicStop(); }
  lastPump = p;
  if (alarm) musicStop();
  musicUpdate(now, beep ? ALARM_HZ : 0);
}
