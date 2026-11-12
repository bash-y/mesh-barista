// Mesh Barista  PR2  -  NODE 1: PUMP STATION  (spec Node A: source / pump zone)
//
// Owns:    3 reservoir water sensors + 3 pump relays (coffee, milk, cream). One pump at a time.
// Depends: Node 2 (pour orders, operator ACK) and Node 3 (cup level). Losing either -> SAFE by itself.
// SAFE:    all pumps OFF, buzzer on, reason broadcast. Leaves SAFE only on an operator ACK (joystick
//          click or dashboard), because a half-poured cup is in an unknown state and must not auto-resume.
//          The ACK needs Node 3 back; without Node 2 the system then runs DEGRADED from the dashboard.
// Radio:   ESP-NOW (barista_mesh.h). No router, no pairing: broadcast, with a one-hop relay.
// Web:     hosts the dashboard (barista_web.h), so it stays reachable here when Node 2 is off.
// Orders:  keeps the order queue. Anyone on the Wi-Fi orders from the dashboard; the operator pours
//          the next order (joystick click or dashboard), and the drink's ingredients pour one by one.
//
// Libraries: ArduinoJson. ESP-NOW and WebServer come with the ESP32 board package.
// Files:     barista_mesh.h, barista_web.h and dashboard_html.h must sit in this sketch folder.

#include <ArduinoJson.h>
#include <esp_task_wdt.h>

// Placeholders: set the same values on all 3 nodes locally. Never share the real ones (report, Wokwi, git).
#define MESH_SSID     "CHANGE_ME_SSID"
#define MESH_PASSWORD "CHANGE_ME_PASSWORD"

const int   NODE_ID = 1;
const char* ZONE    = "pump station";
const char* ING[3]  = {"coffee", "milk", "cream"};

// ---------- pins ----------
const int RELAY_PIN[3] = {25, 26, 27};  // 10k pull-downs keep them LOW while the ESP32 resets
const int RELAY_ON     = HIGH;          // HIGH for active-HIGH relay modules (jumper on H). If a relay clicks
                                        // ON at boot and OFF when a pour starts, yours is active-LOW: use LOW.
const int LEVEL_PIN[3] = {32, 33, 34};  // ADC1 only: ADC2 reads garbage while the mesh radio is on
const int BUZZER_PIN   = 13;
const int BUZZER_ON    = LOW;           // idle level is the opposite, so no current flows while silent
const uint32_t ALARM_HZ = 2700;         // passive buzzer: alarm and test beeps are a tone at this pitch
enum PourSound { POUR_QUIET, POUR_GURGLE, POUR_BASS };
const PourSound POUR_SOUND = POUR_GURGLE;  // while a pump runs: a coffee machine gurgle, or the walking
                                           // bass line under Node 2's melody (POUR_BASS), or nothing

// ---------- tuning (justify these in the report) ----------
const float FLOW_ML_PER_S[3]  = {20.0, 20.0, 20.0};  // calibrate: run each pump 10 s into a measuring cup, mL / 10
// Reservoir levels. Each sensor stands on the bottom of its reservoir, so its 5.07 cm strips see the last
// 5 cm before the pump runs dry: 100 % = 5 cm of liquid or more, 0 % = empty. The strips are not linear,
// so fill each reservoir to the heights below (from the inside bottom) and put the raw values from the
// dashboard's Test tab into LEVEL_RAW, one row per reservoir. Each row must increase.
//                                dry  1.3cm 2.5cm 3.8cm 5.1cm
const int   LEVEL_PCT[5]       = {0,   25,   50,   75,  100};
const int   LEVEL_RAW[3][5]    = {{0, 900, 1300, 1600, 1800},   // coffee  (calibrate: placeholders)
                                  {0, 900, 1300, 1600, 1800},   // milk
                                  {0, 900, 1300, 1600, 1800}};  // cream
const int   LEVEL_SAMPLES     = 16;    // averaged per reading: one ADC sample jumps by ~100
const int   LEVEL_LOCK_PCT    = 10;    // below: that pump is locked (dry-run protection)
const int   LEVEL_UNLOCK_PCT  = 20;    // must refill above this to unlock (hysteresis, no relay chatter)
const int   CUP_FULL_PCT      = 90;    // Node 3 cup reading that stops the pump
const float MAX_POUR_ML       = 300;   // reject orders bigger than the cup
const unsigned long HEARTBEAT_MS = 1000;
const unsigned long WATCHDOG_MS  = 3000;  // loop() frozen this long -> reset, relays off (same as LOST_MS)
const unsigned long LOST_MS      = 3000;  // 3 missed heartbeats, direct or relayed
const unsigned long CUP_STALE_MS = 1500;  // never pour blind longer than this (Node 3 sends 4x/s while pouring)

enum State { NORMAL, DEGRADED, SAFE };
const char* STATE_NAME[] = {"NORMAL", "DEGRADED", "SAFE"};
State  state   = SAFE;   // boot into SAFE: a reset node never restarts a pump by itself
String safeWhy = "boot";

struct Peer { int id; const char* zone; unsigned long lastSeen; bool alive; };
Peer  peers[] = {{2, "control", 0, false}, {3, "output", 0, false}};
Peer& node2   = peers[0];
Peer& node3   = peers[1];

int  levelPct[3] = {0, 0, 0};
bool locked[3]   = {false, false, false};
int  pumping     = -1;   // ingredient being poured, -1 = none
unsigned long pourStart = 0, pourMs = 0;
int  cupPct = 0;         // latest cup level from Node 3
int  levelRaw[3] = {0, 0, 0};          // raw ADC values, shown on the dashboard for calibration
unsigned long buzzTestUntil = 0;       // dashboard buzzer test
uint32_t seq = 0;

#include "barista_mesh.h"
#include "barista_web.h"
#include "barista_music.h"

// ---------- order queue ----------
struct Order { int id; char name[ORDER_NAME_MAX + 1]; int drink; };
const int QUEUE_MAX = 7;                 // the queue message must fit one ESP-NOW frame (250 bytes)
const unsigned long STEP_GAP_MS = 400;   // pause between a drink's ingredients
Order queue[QUEUE_MAX];
int   queueLen = 0, nextOrderId = 1;
Order cur;                               // the order being poured
bool  curActive = false;
int   curStep = -1, lastStartedId = 0;   // curStep: the ingredient being poured (0 coffee .. 2 cream)
unsigned long nextStepAt = 0;            // when to pour the next ingredient, 0 = not waiting
String seenKeys[16];                     // keys of recent orders, to drop duplicate copies
int    seenHead = 0;
void finishOrder(const String& msg);     // used by stopPump, defined with the queue below

// ---------- messaging ----------
void addHeader(JsonDocument& doc) {
  doc["node"] = NODE_ID;
  doc["zone"] = ZONE;
  doc["seq"]  = seq++;
  doc["up"]   = millis();
}

void sendDoc(JsonDocument& doc) { meshSend(doc); }

// Events go to Serial, to this node's dashboard log, and to the mesh for the other nodes' logs.
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
  JsonArray lvl = doc.createNestedArray("lvl");
  JsonArray raw = doc.createNestedArray("raw");
  JsonArray lock = doc.createNestedArray("lock");
  for (int i = 0; i < 3; i++) { lvl.add(levelPct[i]); raw.add(levelRaw[i]); lock.add(locked[i] ? 1 : 0); }
  doc["pump"]  = pumping + 1;  // 0 none, 1 coffee, 2 milk, 3 cream
  if (curActive) doc["ord"] = cur.id;
  doc["state"] = STATE_NAME[state];
  if (state == SAFE) doc["why"] = safeWhy;
  JsonArray alive = doc.createNestedArray("alive");  // link status as this node sees it
  for (auto& p : peers) if (p.alive) alive.add(p.id);
  doc["ip"] = WiFi.softAPIP().toString();            // where this node serves the dashboard
  meshSend(doc);
  String out;
  serializeJson(doc, out);
  webStore(NODE_ID, out);
}

// ---------- pumps ----------
void stopPump(const String& why) {
  if (pumping < 0) return;
  digitalWrite(RELAY_PIN[pumping], !RELAY_ON);
  String name = ING[pumping];
  pumping = -1;
  musicStop();
  gurgleStop();
  logEvent(name + " pump OFF - " + why);
  if (curActive) {
    if (why == "pour done") nextStepAt = millis() + STEP_GAP_MS;  // on to the drink's next ingredient
    else finishOrder(String("order #") + cur.id + " stopped: " + why);
  }
  sendStatus();
}

void startPump(int i, float ml) {
  pumping   = i;
  pourStart = millis();
  pourMs    = ml / FLOW_ML_PER_S[i] * 1000;
  digitalWrite(RELAY_PIN[i], RELAY_ON);
  if (POUR_SOUND == POUR_GURGLE) gurgleStart();
  if (POUR_SOUND == POUR_BASS)   musicPlay(TUNE(TUNE_BASS), true, pourStart);
  logEvent(String(ING[i]) + " pump ON - " + String(ml, 0) + " mL = " + pourMs + " ms");
  sendStatus();
}

void updatePour() {
  if (pumping < 0) return;
  unsigned long now = millis();
  if (cupPct >= CUP_FULL_PCT)                   stopPump("cup full (Node 3)");
  else if (now - node3.lastSeen > CUP_STALE_MS) stopPump("no cup reading from Node 3");
  else if (now - pourStart >= pourMs)           stopPump("pour done");
}

// ---------- state machine ----------
void enterSafe(const String& why) {
  if (state != SAFE) { state = SAFE; safeWhy = why; logEvent("-> SAFE: " + why); }
  if (pumping >= 0) stopPump("SAFE");
  else sendStatus();
}

void updateState() {
  if (state == SAFE) return;
  // DEGRADED: a reservoir is low, or the operator acknowledged running without Node 2
  State s = (locked[0] || locked[1] || locked[2] || !node2.alive) ? DEGRADED : NORMAL;
  if (s != state) { state = s; logEvent(String("-> ") + STATE_NAME[s]); sendStatus(); }
}

void checkPeers() {
  for (auto& p : peers) {
    bool alive = p.lastSeen && millis() - p.lastSeen < LOST_MS;
    if (alive == p.alive) continue;
    p.alive = alive;
    logEvent(String("Node ") + p.id + " (" + p.zone + ") " + (alive ? "ALIVE" : "LOST"));
    if (!alive) enterSafe(String("lost Node ") + p.id + " (" + p.zone + ")");
  }
}

// Interpolate between calibration points: raw[] and pct[] are n matching, increasing values.
int rawToPct(int raw, const int* rawPts, const int* pct, int n) {
  if (raw <= rawPts[0])     return pct[0];
  if (raw >= rawPts[n - 1]) return pct[n - 1];
  for (int i = 1; i < n; i++)
    if (raw < rawPts[i]) return map(raw, rawPts[i - 1], rawPts[i], pct[i - 1], pct[i]);
  return pct[n - 1];
}

void readLevels() {
  for (int i = 0; i < 3; i++) {
    long sum = 0;
    for (int k = 0; k < LEVEL_SAMPLES; k++) sum += analogRead(LEVEL_PIN[i]);
    levelRaw[i] = sum / LEVEL_SAMPLES;
    levelPct[i] = rawToPct(levelRaw[i], LEVEL_RAW[i], LEVEL_PCT, 5);
    if (!locked[i] && levelPct[i] < LEVEL_LOCK_PCT) {
      locked[i] = true;
      logEvent(String(ING[i]) + " reservoir low (" + levelPct[i] + "%) - pump locked");
      if (pumping == i) stopPump("dry-run protection");
    } else if (locked[i] && levelPct[i] > LEVEL_UNLOCK_PCT) {
      locked[i] = false;
      logEvent(String(ING[i]) + " reservoir refilled (" + levelPct[i] + "%) - unlocked");
    }
  }
  updateState();
}

// ---------- order queue ----------
// {"node":1,"seq":9,"queue":[[4,"Ana",1],[5,"Sam",0]],"cur":[3,"Dan",2,0]}   cur: id, name, drink, step
void sendQueue() {
  DynamicJsonDocument doc(768);
  doc["node"] = NODE_ID;
  doc["seq"]  = seq++;
  JsonArray q = doc.createNestedArray("queue");
  for (int i = 0; i < queueLen; i++) {
    JsonArray e = q.createNestedArray();
    e.add(queue[i].id);
    e.add(queue[i].name);
    e.add(queue[i].drink);
  }
  if (curActive) {
    JsonArray c = doc.createNestedArray("cur");
    c.add(cur.id);
    c.add(cur.name);
    c.add(cur.drink);
    c.add(curStep);
  }
  meshSend(doc);
  String out;
  serializeJson(doc, out);
  webQueueStore(out);
}

void finishOrder(const String& msg) {
  curActive  = false;
  curStep    = -1;
  nextStepAt = 0;
  logEvent(msg);
  sendQueue();
  sendStatus();
}

// Pour the drink's next ingredient, or finish the order when there is none left.
void advanceOrder() {
  int s = curStep + 1;
  while (s < 3 && DRINK_ML[cur.drink][s] == 0) s++;
  String tag = String("order #") + cur.id;
  if (s >= 3)                 { finishOrder(tag + " ready: " + cur.name + "'s " + DRINK_NAME[cur.drink]); return; }
  if (state == SAFE)          { finishOrder(tag + " stopped: SAFE"); return; }
  if (locked[s])              { finishOrder(tag + " stopped: " + ING[s] + " reservoir low"); return; }
  if (cupPct >= CUP_FULL_PCT) { finishOrder(tag + " stopped: cup full"); return; }
  curStep = s;
  sendQueue();
  startPump(s, DRINK_ML[cur.drink][s]);
}

void handleOrder(JsonDocument& doc) {
  const char* key = doc["k"] | "";
  if (!*key) return;
  for (auto& k : seenKeys) if (k == key) return;  // a second copy of an order already taken
  seenKeys[seenHead] = key;
  seenHead = (seenHead + 1) % 16;

  Order o = {};
  int n = 0;  // name: printable ASCII only, without quotes or backslashes
  for (const char* c = doc["n"] | ""; *c && n < ORDER_NAME_MAX; c++)
    if (*c >= 32 && *c < 127 && *c != '"' && *c != '\\' && (n || *c != ' ')) o.name[n++] = *c;
  o.name[n] = 0;
  o.drink   = doc["d"] | -1;
  if (!n || o.drink < 0 || o.drink >= DRINKS) { logEvent("order refused: bad request"); return; }
  if (queueLen >= QUEUE_MAX) { logEvent(String("order refused: the queue is full (") + QUEUE_MAX + " waiting)"); return; }
  o.id = nextOrderId++;
  queue[queueLen++] = o;
  logEvent(String("order #") + o.id + ": " + o.name + " - " + DRINK_NAME[o.drink]);
  sendQueue();
}

// Start the order at the head of the queue. `id` must name it, so a duplicate copy of this command
// (relayed twice) or one sent from a page that is out of date does nothing.
void handleNext(int id) {
  if (id == lastStartedId) return;  // a second copy of a command already carried out
  if (curActive)              { logEvent("next order refused: an order is pouring"); return; }
  if (!queueLen)              { logEvent("next order refused: the queue is empty"); return; }
  if (queue[0].id != id)      { logEvent("next order refused: the queue changed, try again"); return; }
  if (state == SAFE)          { logEvent("next order refused: SAFE (" + safeWhy + ")"); return; }
  if (pumping >= 0)           { logEvent("next order refused: already pouring"); return; }
  if (cupPct >= CUP_FULL_PCT) { logEvent("next order refused: cup full"); return; }
  cur = queue[0];
  for (int i = 1; i < queueLen; i++) queue[i - 1] = queue[i];
  queueLen--;
  curActive     = true;
  curStep       = -1;
  lastStartedId = cur.id;
  logEvent(String("order #") + cur.id + " pouring: " + cur.name + " - " + DRINK_NAME[cur.drink]);
  advanceOrder();
}

void handleDrop(int id) {
  for (int i = 0; i < queueLen; i++) {
    if (queue[i].id != id) continue;
    logEvent(String("order #") + id + " removed: " + queue[i].name);
    for (int j = i + 1; j < queueLen; j++) queue[j - 1] = queue[j];
    queueLen--;
    sendQueue();
    return;
  }
}

// ---------- commands: from Node 2's joystick, or from the dashboard on any node ----------
void handlePour(int i, float ml) {
  if (i < 0 || i > 2 || ml <= 0 || ml > MAX_POUR_ML) { logEvent("pour refused: bad request"); return; }
  if (state == SAFE)          { logEvent("pour refused: SAFE (" + safeWhy + ")"); return; }
  if (locked[i])              { logEvent(String("pour refused: ") + ING[i] + " reservoir low"); return; }
  if (pumping >= 0)           { logEvent("pour refused: already pouring"); return; }
  if (curActive)              { logEvent("pour refused: an order is pouring"); return; }
  if (cupPct >= CUP_FULL_PCT) { logEvent("pour refused: cup full"); return; }
  startPump(i, ml);
}

void handleAck() {
  if (state != SAFE) return;
  // Node 3's cup reading is what makes a pour safe, so it must be back. Node 2 is only the joystick
  // and gateway: every node hosts the dashboard, so the operator may carry on without it (DEGRADED).
  if (!node3.alive) { logEvent("ACK rejected: Node 3 still LOST (no cup reading)"); return; }
  state = NORMAL;
  logEvent(node2.alive ? "ACK accepted - leaving SAFE" : "ACK accepted - running without Node 2");
  updateState();
  sendStatus();
}

void handleCmd(const char* cmd, int to, int ing, float ml) {
  if (!strcmp(cmd, "pour"))      handlePour(ing, ml);
  else if (!strcmp(cmd, "ack"))  handleAck();
  else if (!strcmp(cmd, "stop")) {
    stopPump("stopped from the dashboard");
    if (curActive) finishOrder(String("order #") + cur.id + " stopped from the dashboard");  // between ingredients
  }
  else if (!strcmp(cmd, "trip")) enterSafe("tripped from the dashboard");
  else if (!strcmp(cmd, "next")) handleNext(ing);  // ing carries the order id
  else if (!strcmp(cmd, "drop")) handleDrop(ing);
  else if (!strcmp(cmd, "buzz") && to == NODE_ID) buzzTestUntil = millis() + 1000;
  // Demo aid: make node `to` act as if node `ing` were out of range, to show the relay path.
  else if (!strcmp(cmd, "deaf") && to == NODE_ID && ing >= 1 && ing <= 3) {
    meshDeaf[ing] = !meshDeaf[ing];
    logEvent(String("Node ") + ing + (meshDeaf[ing] ? " treated as out of range" : " back in range"));
  }
}

void onMeshMessage(const String& raw, JsonDocument& doc, int src, int hop, int via) {
  for (auto& p : peers) if (p.id == src) p.lastSeen = millis();
  checkPeers();  // mark the sender ALIVE before acting on its command
  if (!doc["evt"].isNull())   webLog(String("Node ") + src + ": " + doc["evt"].as<const char*>());
  if (!doc["state"].isNull()) webStore(src, raw);  // a status message: keep it for the dashboard
  if (src == 3) cupPct = doc["cup"] | cupPct;
  if (!doc["cmd"].isNull()) {
    if (!strcmp(doc["cmd"] | "", "order")) handleOrder(doc);
    else handleCmd(doc["cmd"] | "", doc["to"] | 0, doc["ing"] | -1, doc["ml"] | 0.0f);
  }
}

void setup() {
  for (int i = 0; i < 3; i++) { pinMode(RELAY_PIN[i], OUTPUT); digitalWrite(RELAY_PIN[i], !RELAY_ON); }  // pumps OFF first
  buzzerOff();
  Serial.begin(115200);

  meshBegin(MESH_SSID, MESH_PASSWORD);
  webBegin();

  readLevels();
  logEvent("boot -> SAFE, waiting for Nodes 2 + 3 and an operator ACK");
  // Say why the last run ended, so a watchdog reset or a brownout from a pump shows in the log.
  esp_reset_reason_t why = esp_reset_reason();
  if (why == ESP_RST_TASK_WDT || why == ESP_RST_INT_WDT || why == ESP_RST_WDT) logEvent("restarted by the watchdog: the program froze");
  else if (why == ESP_RST_BROWNOUT) logEvent("restarted by a brownout: supply voltage dipped (pump noise?)");
  else if (why == ESP_RST_PANIC)    logEvent("restarted after a crash");

  // Watchdog: if loop() stops running for WATCHDOG_MS, the chip resets. setup() turns every relay off
  // first, so a frozen program can never leave a pump running.
  esp_task_wdt_config_t wdt = {};
  wdt.timeout_ms     = WATCHDOG_MS;
  wdt.trigger_panic  = true;  // reset, don't just print a warning
  esp_task_wdt_reconfigure(&wdt);
  esp_task_wdt_add(NULL);      // watch this task (the one running loop())
}

void loop() {
  static unsigned long lastRead = 0, lastBeat = 0, lastQueue = 0;
  esp_task_wdt_reset();  // still alive
  meshLoop();
  webLoop();
  unsigned long now = millis();
  checkPeers();
  if (now - lastRead >= 200) { lastRead = now; readLevels(); }
  updatePour();
  if (now - lastBeat >= HEARTBEAT_MS) { lastBeat = now; sendStatus(); }
  if (now - lastQueue >= 2000) { lastQueue = now; sendQueue(); }  // so a node that just joined has it too
  if (curActive && pumping < 0 && nextStepAt && now >= nextStepAt) { nextStepAt = 0; advanceOrder(); }
  bool alarm = state == SAFE && safeWhy != "boot";  // a fresh boot is not a fault: stay quiet until one happens
  bool beep  = now < buzzTestUntil || (alarm && (now / 300) % 2);
  if (alarm) { musicStop(); gurgleStop(); }
  musicUpdate(now, beep ? ALARM_HZ : 0);
}
