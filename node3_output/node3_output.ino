// Mesh Barista  PR2  -  NODE 3: OUTPUT  (spec Node B: distribution zone)
//
// Owns:    cup water sensor, status OLED, RGB status LED.
// Role:    its cup reading is what stops Node 1's pump (the cross-node control decision).
//          It reports the cup 4x/s while a pump runs and 1x/s when idle.
// Shows:   LED orange/white/yellow = coffee/milk/cream pouring, green = ready, flashing red = error.
// Radio:   ESP-NOW (barista_mesh.h). No router, no pairing: broadcast, with a one-hop relay.
// Web:     hosts the dashboard (barista_web.h), so it stays reachable here when Node 2 is off.
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

const int   NODE_ID = 3;
const char* ZONE    = "output";
const char* ING[3]  = {"coffee", "milk", "cream"};

// ---------- pins ----------
const int CUP_PIN    = 32;            // ADC1 only: ADC2 reads garbage while the mesh radio is on
const int RGB_PIN[3] = {25, 26, 27};  // R, G, B of a common-anode LED (V pin on 3V3): LOW = on

// ---------- tuning ----------
const int CUP_RAW_DRY  = 0;           // calibrate: analogRead() with the cup sensor dry
const int CUP_RAW_FULL = 1800;        // calibrate: analogRead() with the cup at its max fill line
const unsigned long HEARTBEAT_MS = 1000;
const unsigned long FAST_MS      = 250;   // while a pump runs, Node 1 needs a fresh cup level
const unsigned long LOST_MS      = 3000;  // 3 missed heartbeats, direct or relayed

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;

struct Peer { int id; const char* zone; unsigned long lastSeen; bool alive; };
Peer  peers[] = {{1, "pump station", 0, false}, {2, "control", 0, false}};
Peer& node1   = peers[0];
Peer& node2   = peers[1];

int    cupPct  = 0, cupRaw = 0;                          // cupRaw: raw ADC value, for calibration
unsigned long ledTestUntil = 0;                          // dashboard LED test
String n1State = "SAFE", n1Why = "waiting for Node 1";  // latest from Node 1
int    n1Pump  = 0;                                      // 0 none, 1 coffee, 2 milk, 3 cream
String view = "SAFE", viewWhy = "";                      // system state as this node sees it
uint32_t seq = 0;

#include "barista_mesh.h"
#include "barista_web.h"

// ---------- messaging ----------
void addHeader(JsonDocument& doc) {
  doc["node"] = NODE_ID;
  doc["zone"] = ZONE;
  doc["seq"]  = seq++;
  doc["up"]   = millis();
}

void sendDoc(JsonDocument& doc) { meshSend(doc); }

void logEvent(const String& msg) {
  Serial.printf("[%8.1fs] %s\n", millis() / 1000.0, msg.c_str());
  webLog(String("Node ") + NODE_ID + ": " + msg);
  DynamicJsonDocument doc(256);
  addHeader(doc);
  doc["evt"] = msg;
  sendDoc(doc);
}

void sendStatus() {
  DynamicJsonDocument doc(1024);
  addHeader(doc);
  doc["cup"]   = cupPct;
  doc["raw"]   = cupRaw;
  doc["state"] = view;
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

void updateView() {
  if (!node1.alive)      { view = "SAFE"; viewWhy = node1.lastSeen ? "Node 1 LOST" : "waiting for Node 1"; }
  else { view = n1State; viewWhy = n1State == "SAFE" ? n1Why : node2.alive ? String("") : String("Node 2 LOST"); }
}

void handleCmd(const char* cmd, int to, int ing, float ml) {
  if (!strcmp(cmd, "led") && to == NODE_ID) ledTestUntil = millis() + 2100;  // red, green, blue: 0.7 s each
  // Demo aid: make node `to` act as if node `ing` were out of range, to show the relay path.
  else if (!strcmp(cmd, "deaf") && to == NODE_ID && ing >= 1 && ing <= 3) {
    meshDeaf[ing] = !meshDeaf[ing];
    logEvent(String("Node ") + ing + (meshDeaf[ing] ? " treated as out of range" : " back in range"));
  }
}

void onMeshMessage(const String& raw, JsonDocument& doc, int src, int hop, int via) {
  for (auto& p : peers) if (p.id == src) p.lastSeen = millis();
  checkPeers();
  if (!doc["evt"].isNull())   webLog(String("Node ") + src + ": " + doc["evt"].as<const char*>());
  if (!doc["state"].isNull()) webStore(src, raw);  // a status message: keep it for the dashboard
  if (!doc["cmd"].isNull())   handleCmd(doc["cmd"] | "", doc["to"] | 0, doc["ing"] | -1, doc["ml"] | 0.0f);
  if (src == 1 && !doc["state"].isNull()) {
    n1State = doc["state"].as<const char*>();
    n1Why   = doc["why"] | "";
    n1Pump  = doc["pump"] | 0;
  }
}

// ---------- outputs ----------
void setColor(int r, int g, int b) {  // common-anode: 255 = off
  static int last = -1;
  int rgb = r << 16 | g << 8 | b;
  if (rgb == last) return;  // only touch the PWM when the color changes
  last = rgb;
  analogWrite(RGB_PIN[0], 255 - r);
  analogWrite(RGB_PIN[1], 255 - g);
  analogWrite(RGB_PIN[2], 255 - b);
}

void updateLed() {
  unsigned long now = millis();
  if (now < ledTestUntil) {  // dashboard test: one color per pin, to check the wiring
    int k = 2 - (ledTestUntil - now - 1) / 700;
    setColor(k == 0 ? 255 : 0, k == 1 ? 255 : 0, k == 2 ? 255 : 0);
    return;
  }
  int pump = node1.alive ? n1Pump : 0;
  if      (pump == 1)        setColor(255, 60, 0);     // coffee: orange
  else if (pump == 2)        setColor(255, 255, 255);  // milk: white
  else if (pump == 3)        setColor(255, 180, 0);    // cream: yellow
  else if (view != "NORMAL") setColor((millis() / 250) % 2 ? 255 : 0, 0, 0);  // error: flashing red
  else                       setColor(0, 255, 0);      // ready: green
}

void updateOled() {
  if (!oledOk) return;
  int pump = node1.alive ? n1Pump : 0;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("Node 3  ");
  oled.println(WEB_HOST);  // the dashboard address
  oled.setTextSize(2);
  oled.print("Cup ");
  oled.print(cupPct);
  oled.println("%");
  oled.setTextSize(1);
  oled.print("Pump:  ");
  oled.println(pump ? ING[pump - 1] : "off");
  oled.print("State: ");
  oled.println(view);
  oled.print(node1.alive ? "N1 OK    " : "N1 LOST  ");
  oled.println(node2.alive ? "N2 OK" : "N2 LOST");
  oled.println(viewWhy);
  oled.display();
}

void setup() {
  setColor(0, 0, 0);
  Serial.begin(115200);
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (!oledOk) Serial.println("OLED not found at 0x3C - running without it");

  meshBegin(MESH_SSID, MESH_PASSWORD);
  webBegin();
  logEvent("boot");
}

void loop() {
  static unsigned long lastSend = 0, lastDraw = 0;
  meshLoop();
  webLoop();
  unsigned long now = millis();
  checkPeers();
  updateView();
  bool pouring = node1.alive && n1Pump != 0;
  if (now - lastSend >= (pouring ? FAST_MS : HEARTBEAT_MS)) {
    lastSend = now;
    cupRaw = analogRead(CUP_PIN);
    cupPct = constrain(map(cupRaw, CUP_RAW_DRY, CUP_RAW_FULL, 0, 100), 0, 100);
    sendStatus();
  }
  updateLed();
  if (now - lastDraw >= 250) { lastDraw = now; updateOled(); }
}
