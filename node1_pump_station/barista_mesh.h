// Mesh Barista: the ESP-NOW mesh, identical on all three nodes.
// The master copy lives in dashboard_src/; build_assets.py copies it into each sketch folder.
//
// ESP-NOW needs no router and no pairing: every message is a broadcast, so no node has to know
// another's MAC address. What it does not give us is forwarding, so this file adds it:
//
//   send      a JSON message, stamped with this node's id and a sequence number, broadcast to all
//   dedupe    each node remembers the last sequence number per sender and ignores repeats
//   relay     a message heard first-hand (hop 0) is rebroadcast once as hop 1, naming this node
//             as the relay. A hop-1 message is never relayed again, so a message can't circulate.
//   links     from the hops it hears, each node knows which peers it reaches directly and which
//             only through the third node. That is what the dashboard draws.
//
// ESP-NOW rides on the Wi-Fi radio, so every node must use the same channel (MESH_CHANNEL) and
// the access point that serves the dashboard must be on that channel too.
//
// Include it once, from the sketch, after NODE_ID is defined.
#include <WiFi.h>
#include <esp_now.h>

// The sketch provides this; it is called from meshLoop(), never from the radio callback.
void onMeshMessage(const String& raw, JsonDocument& doc, int src, int hop, int via);

const int MESH_CHANNEL = 1;              // all three nodes, and their access points, must match
const int MESH_MAX     = 250;            // ESP-NOW's payload limit
const unsigned long LINK_FORGET_MS = 3000;  // a path not heard for this long is no longer current (matches LOST_MS)

const uint8_t MESH_BCAST[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

uint32_t meshSeq  = 0;
bool     meshUp   = false;
uint32_t meshSent = 0, meshRelayed = 0, meshDropped = 0, meshTooBig = 0;

struct MeshLink {
  long          lastSeq;     // last sequence number accepted from this node, -1 = nothing yet
  unsigned long directAt;    // when a hop-0 message from it last arrived
  unsigned long viaAt;       // when a relayed one last arrived
  int           via;         // which node relayed it
};
MeshLink meshLink[4];

// Demo aid: pretend a node is out of range by ignoring what it sends first-hand. Its messages
// then only arrive relayed by the third node, which is the multi-hop path the dashboard draws.
bool meshDeaf[4] = {false, false, false, false};

// ---------- receive: the radio callback only copies bytes into a queue ----------
const int MESH_Q = 16;
char          meshQ[MESH_Q][MESH_MAX + 1];
volatile int  meshQHead = 0, meshQTail = 0;

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void meshRecv(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
#else
void meshRecv(const uint8_t* mac, const uint8_t* data, int len) {
#endif
  if (len <= 0 || len > MESH_MAX) return;
  // Both peers relay everything they hear, so this node's own messages come straight back. "node" is
  // always the first key, so dropping them here costs one compare and saves two thirds of the queue.
  char self[10];
  int  n = snprintf(self, sizeof self, "{\"node\":%d", NODE_ID);
  if (len > n && !memcmp(data, self, n)) return;
  int next = (meshQHead + 1) % MESH_Q;
  if (next == meshQTail) { meshDropped++; return; }  // queue full: the loop is behind
  memcpy(meshQ[meshQHead], data, len);
  meshQ[meshQHead][len] = 0;
  meshQHead = next;
}

// ---------- send ----------
bool meshSendRaw(const String& out) {
  if (out.length() > MESH_MAX) { meshTooBig++; return false; }  // would be cut off: don't send it
  if (!meshUp) return false;
  bool ok = esp_now_send(MESH_BCAST, (const uint8_t*)out.c_str(), out.length()) == ESP_OK;
  if (ok) meshSent++;
  return ok;
}

// Stamp a message as this node's and broadcast it. Fills in "node" and "seq" if the caller has not.
bool meshSend(JsonDocument& doc) {
  if (doc["node"].isNull()) doc["node"] = NODE_ID;
  if (doc["seq"].isNull())  doc["seq"]  = meshSeq++;
  doc["h"] = 0;  // hop count: 0 straight from the node that made it
  String out;
  serializeJson(doc, out);
  return meshSendRaw(out);
}

// ---------- links, as this node currently hears them ----------
bool meshDirect(int n) { return n >= 1 && n <= 3 && meshLink[n].directAt && millis() - meshLink[n].directAt < LINK_FORGET_MS; }
int  meshVia(int n) {
  if (n < 1 || n > 3 || meshDirect(n)) return 0;
  return (meshLink[n].viaAt && millis() - meshLink[n].viaAt < LINK_FORGET_MS) ? meshLink[n].via : 0;
}

// {"1":{"d":1,"v":0},"2":{"d":0,"v":3},"3":{"d":1,"v":0}}   d = direct, v = relayed by that node
String meshLinksJson() {
  String s = "{";
  for (int n = 1; n <= 3; n++) {
    if (n > 1) s += ",";
    s += "\"";
    s += String(n);
    s += "\":{\"d\":";
    s += meshDirect(n) ? "1" : "0";
    s += ",\"v\":";
    s += String(meshVia(n));
    s += "}";
  }
  return s + "}";
}

// ---------- the queue, drained once per loop ----------
void meshLoop() {
  while (meshQTail != meshQHead) {
    String raw = meshQ[meshQTail];
    meshQTail = (meshQTail + 1) % MESH_Q;

    DynamicJsonDocument doc(1024);
    if (deserializeJson(doc, raw)) { meshDropped++; continue; }
    int  src = doc["node"] | 0;
    int  hop = doc["h"] | 0;
    int  via = doc["v"] | 0;
    long seq = doc["seq"] | -1;
    if (src < 1 || src > 3 || src == NODE_ID || seq < 0) continue;  // junk, or this node's own echo
    if (hop == 0 && meshDeaf[src]) continue;                        // "out of range" for the demo

    MeshLink& L = meshLink[src];
    if (seq == L.lastSeq) continue;  // already seen it, by the other path
    L.lastSeq = seq;
    if (hop == 0) L.directAt = millis();
    else          { L.viaAt = millis(); L.via = via; }

    if (hop == 0) {  // heard first-hand: pass it on once, so a node out of range still gets it
      doc["h"] = 1;
      doc["v"] = NODE_ID;
      String out;
      serializeJson(doc, out);
      if (meshSendRaw(out)) meshRelayed++;
    }
    onMeshMessage(raw, doc, src, hop, via);
  }
}

void meshBegin(const char* ssid, const char* password) {
  WiFi.mode(WIFI_AP);
  // Every node is an access point with the same name, password and address. A phone or laptop joins
  // whichever node is in range, and http://192.168.4.1 is always the dashboard, even with a node off.
  IPAddress ip(192, 168, 4, 1), gw(192, 168, 4, 1), mask(255, 255, 255, 0);
  WiFi.softAPConfig(ip, gw, mask);
  WiFi.softAP(ssid, password, MESH_CHANNEL);  // same name on all three, so a phone roams between them
  WiFi.setSleep(false);                       // sleep would make the node miss broadcasts

  if (esp_now_init() != ESP_OK) { Serial.println("ESP-NOW failed to start"); return; }
  esp_now_register_recv_cb(meshRecv);
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, MESH_BCAST, 6);
  peer.channel = MESH_CHANNEL;
  peer.ifidx   = WIFI_IF_AP;   // send on the same interface the access point uses
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) { Serial.println("ESP-NOW broadcast peer failed"); return; }

  meshUp = true;
  for (int n = 0; n < 4; n++) meshLink[n] = {-1, 0, 0, 0};
  Serial.printf("ESP-NOW up on channel %d, node %d, AP %s\n", MESH_CHANNEL, NODE_ID, ip.toString().c_str());
}
