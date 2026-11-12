// Mesh Barista: the web dashboard, identical on all three nodes.
// The master copy lives in dashboard_src/; build_assets.py copies it into each sketch folder.
//
// Every node is a Wi-Fi access point with the same name and hosts the same page, so the dashboard
// keeps working from Node 1 or Node 3 when Node 2 is off. To open it: join the Wi-Fi
// (MESH_SSID / MESH_PASSWORD) and browse to http://barista.io (or http://192.168.4.1).
// Each node also answers every DNS lookup with its own address, which is what makes the name work.
//
//   /      the page (dashboard_html.h, gzipped)
//   /data  JSON: the latest status from every node, this node's links, and the event log
//   /cmd   a test command (c, to, ing, ml): broadcast to the mesh and run on this node
//
// Include it once, from the sketch, after barista_mesh.h.
#include <WebServer.h>
#include <DNSServer.h>
#include "dashboard_html.h"

// provided by each sketch
void handleCmd(const char* cmd, int to, int ing, float ml);  // acts only on the commands meant for this node
void addHeader(JsonDocument& doc);

const char* WEB_HOST = "barista.io";  // the name to type; any other name lands on the dashboard too

WebServer webServer(80);
DNSServer webDns;

String        webStatus[4];  // latest status JSON per node, index = node number (this node included)
unsigned long webSeen[4];    // millis() when it arrived, 0 = never

struct WebEvent { unsigned long t; String m; };
const int WEB_LOG_N = 16;
WebEvent  webEvents[WEB_LOG_N];
int       webLogHead = 0;

void webLog(const String& msg) {
  webEvents[webLogHead].t = millis();
  webEvents[webLogHead].m = msg;
  webLogHead = (webLogHead + 1) % WEB_LOG_N;
}

void webStore(int node, const String& status) {
  if (node < 1 || node > 3) return;
  webStatus[node] = status;
  webSeen[node]   = millis();
}

void webPage() {
  webServer.sendHeader("Content-Encoding", "gzip");
  webServer.send_P(200, "text/html", (const char*)DASHBOARD_HTML_GZ, DASHBOARD_HTML_GZ_LEN);
}

void webData() {
  unsigned long now = millis();
  String out = "{\"me\":";
  out += String(NODE_ID);
  out += ",\"now\":";
  out += String(now);
  out += ",\"nodes\":{";
  for (int n = 1; n <= 3; n++) {
    if (n > 1) out += ",";
    out += "\"";
    out += String(n);
    out += "\":{\"age\":";
    out += webSeen[n] ? String(now - webSeen[n]) : String(-1);
    out += ",\"s\":";
    out += webStatus[n].length() ? webStatus[n] : String("null");
    out += "}";
  }
  out += "},\"links\":";
  out += meshLinksJson();
  out += ",\"deaf\":[";
  for (int n = 1; n <= 3; n++) out += String(n > 1 ? "," : "") + (meshDeaf[n] ? "1" : "0");
  out += "],\"radio\":{\"sent\":";
  out += String(meshSent);
  out += ",\"relayed\":";
  out += String(meshRelayed);
  out += ",\"dropped\":";
  out += String(meshDropped);
  out += ",\"toobig\":";
  out += String(meshTooBig);
  out += "},\"log\":[";
  bool first = true;
  for (int i = 0; i < WEB_LOG_N; i++) {  // oldest first
    WebEvent& e = webEvents[(webLogHead + i) % WEB_LOG_N];
    if (!e.m.length()) continue;
    if (!first) out += ",";
    first = false;
    out += "{\"t\":";
    out += String(e.t);
    out += ",\"m\":\"";
    for (unsigned k = 0; k < e.m.length(); k++) {
      char c = e.m[k];
      if (c == '"' || c == '\\') out += '\\';
      if ((unsigned char)c >= ' ') out += c;
    }
    out += "\"}";
  }
  out += "]}";
  // The page switches to another node's address when this one stops answering, so allow cross-origin reads.
  webServer.sendHeader("Access-Control-Allow-Origin", "*");
  webServer.send(200, "application/json", out);
}

void webCmd() {
  String cmd = webServer.arg("c");
  int    to  = webServer.arg("to").toInt();
  int    ing = webServer.arg("ing").toInt();
  float  ml  = webServer.arg("ml").toFloat();
  webServer.sendHeader("Access-Control-Allow-Origin", "*");
  if (cmd.length() < 2 || cmd.length() > 8) { webServer.send(400, "text/plain", "bad command"); return; }
  DynamicJsonDocument doc(256);
  addHeader(doc);
  doc["cmd"] = cmd;
  doc["to"]  = to;
  doc["ing"] = ing;
  doc["ml"]  = ml;
  meshSend(doc);                         // the other nodes act on it...
  handleCmd(cmd.c_str(), to, ing, ml);   // ...and so does this one. Range checks happen where it runs.
  webServer.send(200, "text/plain", "sent");
}

void webBegin() {
  webServer.on("/", webPage);
  webServer.on("/data", webData);
  webServer.on("/cmd", webCmd);
  // Anything else (a phone's "is there internet?" probe, a mistyped path) is sent to the dashboard.
  webServer.onNotFound([]() {
    webServer.sendHeader("Location", String("http://") + WEB_HOST + "/");
    webServer.send(302, "text/plain", "");
  });
  webServer.begin();
  webDns.start(53, "*", WiFi.softAPIP());  // answer every name with this node's address
  Serial.print("Dashboard: join the Wi-Fi, then open http://");
  Serial.print(WEB_HOST);
  Serial.print("  (or http://");
  Serial.print(WiFi.softAPIP().toString());
  Serial.println(")");
}

void webLoop() {
  webDns.processNextRequest();
  webServer.handleClient();
}
