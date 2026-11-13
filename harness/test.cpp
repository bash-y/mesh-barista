// Runs the three real sketches together over a fake mesh and checks the Project 2 behaviors.
#include <type_traits>
#include "WiFi.h"
#include "esp_now.h"
#include <ArduinoJson.h>
#include "Adafruit_GFX.h"
#include "Adafruit_SSD1306.h"
#include "WebServer.h"
#include "DNSServer.h"
#include "../node1_pump_station/dashboard_html.h"  // once, globally: it has an include guard
#include <cassert>
#include <iostream>
#include <fstream>

namespace n1 {
#include "../node1_pump_station/node1_pump_station.ino"
}
namespace n2 {
#include "../node2_control_center/node2_control_center.ino"
}
namespace n3 {
#include "../node3_output/node3_output.ino"
}

const int N1 = 0, N2 = 1, N3 = 2;
double cupMl = 0;
bool buzz1 = false, buzz2 = false, redOn = false, redOff = false;

bool anyRelay() { return pinOut[N1][25] || pinOut[N1][26] || pinOut[N1][27]; }

void run(unsigned long ms);
void run(unsigned long ms) {
  for (unsigned long t = 0; t < ms; t += 5) {
    fakeMillis += 5;
    if (anyRelay()) cupMl += 20.0 * 0.005;                 // 20 mL/s into a 240 mL cup
    analogVal[N3][32] = (int)(std::min(cupMl, 240.0) / 240 * 1800);
    if (nodeUp[N1]) { curNode = N1; n1::loop(); }
    if (nodeUp[N2]) { curNode = N2; n2::loop(); }
    if (nodeUp[N3]) { curNode = N3; n3::loop(); }
    // invariants: SAFE means every pump is off, and never two pumps at once
    assert(pinOut[N1][25] + pinOut[N1][26] + pinOut[N1][27] <= 1);
    if (n1::state == n1::SAFE) assert(!anyRelay());
    if (nodeUp[N1] && pinOut[N1][13] == LOW) buzz1 = true;  // buzzers are low-trigger
    if (nodeUp[N2] && pinOut[N2][25] == LOW) buzz2 = true;
    if (pinOut[N3][26] == 255 && pinOut[N3][27] == 255) (pinOut[N3][25] == 0 ? redOn : redOff) = true;
  }
}
void click() { pinIn[N2][27] = LOW; run(60); pinIn[N2][27] = HIGH; run(400); }
void pushX(int v) { analogVal[N2][34] = v; run(60); analogVal[N2][34] = 1900; run(60); }
void pushY(int v) { analogVal[N2][35] = v; run(60); analogVal[N2][35] = 1900; run(60); }
void quiet() { buzz1 = buzz2 = redOn = redOff = false; }
bool log2(const char* s) { for (auto& e : n2::webEvents) if (e.m.find(s) != std::string::npos) return true; return false; }
bool log1(const char* s) { for (auto& e : n1::webEvents) if (e.m.find(s) != std::string::npos) return true; return false; }
bool log3(const char* s) { for (auto& e : n3::webEvents) if (e.m.find(s) != std::string::npos) return true; return false; }
// An HTTP request to one node's web server, as the dashboard page would make it.
void run(unsigned long ms);
std::string web(int node, const char* path, std::map<std::string, std::string> args = {}) {
  run(10);                       // handleClient() is called from loop(), never between loops
  curNode = node;
  auto& w = *webOf[node];
  w.args = args; w.code = 0; w.body.clear(); w.headers.clear();
  w.routes.at(path)();
  return w.body;
}
bool has(const std::string& s, const char* x) { return s.find(x) != std::string::npos; }
// /data must be valid JSON; the stub parser is strict enough to catch a broken string build.
std::string data(int node) {
  std::string b = web(node, "/data");
  JsonDocument d;
  assert(!deserializeJson(d, b) && webOf[node]->code == 200 && webOf[node]->headers.count("Access-Control-Allow-Origin"));
  return b;
}
bool dash(const char* s) {  // text in the most recent dashboard block
  auto& o = serialOut[N2];
  return o.find(s, o.rfind("=============== MESH")) != std::string::npos;
}
bool led(int r, int g, int b) { return pinOut[N3][25] == 255 - r && pinOut[N3][26] == 255 - g && pinOut[N3][27] == 255 - b; }
void ok(const char* name) { std::cout << "ok  " << name << std::endl; }

int main() {
  for (int p : {32, 33, 34}) analogVal[N1][p] = 1400;       // reservoirs ~77 %
  analogVal[N2][34] = analogVal[N2][35] = 1900;             // joystick centered
  pinIn[N2][27] = HIGH;
  curNode = N1; n1::setup();
  curNode = N2; n2::setup();
  curNode = N3; n3::setup();

  run(2500);
  assert(n1::state == n1::SAFE && n1::safeWhy == "boot" && n2::sysState == "SAFE" && n3::view == "SAFE");
  assert(n2::affected == "pump station: boot" && !buzz1 && !buzz2);
  click();
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL" && n3::view == "NORMAL" && led(0, 255, 0));
  assert(log2("Node 1: ACK accepted"));
  ok("boot in SAFE (quiet), operator ACK -> NORMAL, LED green");

  pushX(3500);            // right -> milk
  pushY(500); pushY(500); // up twice -> 80 mL
  assert(n2::sel == 1 && n2::ml == 80);
  click();
  assert(pinOut[N1][26] == HIGH && !pinOut[N1][25] && !pinOut[N1][27] && n2::pump == 2 && led(255, 255, 255));
  assert(oledText[N3].find("Pump:  milk") != std::string::npos && oledText[N2].find(">milk") != std::string::npos);
  run(4000);
  assert(!anyRelay() && log2("Node 1: milk pump OFF - pour done") && led(0, 255, 0));
  assert(cupMl > 75 && cupMl < 85);
  ok("joystick menu -> timed 80 mL milk pour, LED white then green");

  n2::ml = 240;
  click();
  run(9000);
  assert(!anyRelay() && log2("Node 1: milk pump OFF - cup full (Node 3)") && cupMl < 225);
  click();
  assert(log2("Node 1: pour refused: cup full"));
  ok("cup-full reading from Node 3 stops Node 1's pump");

  cupMl = 0; run(1200);
  analogVal[N1][32] = 100;  // coffee reservoir ~5 %
  run(1500);
  assert(n1::state == n1::DEGRADED && n2::sysState == "DEGRADED");
  n2::sel = 0; n2::ml = 30; click();
  assert(log2("Node 1: pour refused: coffee reservoir low") && !anyRelay());
  n2::sel = 2; click();
  assert(pinOut[N1][27] == HIGH && led(255, 180, 0));
  run(2000);
  analogVal[N1][32] = 300;  // ~16 %: inside the hysteresis band, stays locked
  run(500);
  assert(n1::locked[0]);
  analogVal[N1][32] = 1400;
  run(1500);
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL");
  ok("dry-run lock with hysteresis, DEGRADED still pours other ingredients");

  cupMl = 0; run(1200); quiet();
  n2::sel = 0; n2::ml = 200; click();
  assert(pinOut[N1][25] == HIGH);
  run(600);
  nodeUp[N3] = false;                                   // FAULT: Node 3 dies mid-pour
  run(2000);
  assert(!anyRelay());                                  // stopped on stale cup data, before the LOST timeout
  run(4500);
  assert(n1::state == n1::SAFE && n1::safeWhy == "lost Node 3 (output)" && buzz1 && buzz2);
  assert(n2::sysState == "SAFE" && n2::affected == "output (Node 3) LOST");
  assert(dash("Node 3  output        LOST") && dash("AFFECTED ZONE: output (Node 3) LOST"));
  click();
  assert(log2("Node 1: ACK rejected: Node 3 still LOST") && n1::state == n1::SAFE);
  nodeUp[N3] = true; run(2500); click(); quiet(); run(1000);
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL" && !buzz1 && !buzz2);
  ok("Node 3 lost mid-pour: pump off, SAFE, both buzzers, zone named, ACK only after recovery");

  nodeUp[N2] = false;                                   // FAULT: gateway dies
  run(6500);
  assert(n1::state == n1::SAFE && n1::safeWhy == "lost Node 2 (control)" && buzz1);
  assert(n3::view == "SAFE" && n3::viewWhy == "lost Node 2 (control)" && redOn && redOff);
  nodeUp[N2] = true; run(2500); click(); quiet(); run(1000);
  assert(n1::state == n1::NORMAL && !buzz1);
  ok("Node 2 lost: Node 1 goes SAFE alone with its own buzzer, Node 3 flashes red");

  nodeUp[N1] = false;                                   // FAULT: pump station dies
  run(6500);
  assert(n2::sysState == "SAFE" && n2::affected == "pump station (Node 1) LOST" && buzz2 && n3::viewWhy == "Node 1 LOST");
  click();
  assert(log2("click ignored: Node 1 not connected"));
  nodeUp[N1] = true; run(2500);
  assert(n1::state == n1::SAFE);                        // it lost its peers too, so it comes back SAFE
  click(); run(1000);
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL");
  ok("Node 1 lost: dashboard names the pump station, recovery needs ACK");

  assert(dash("Node 1: direct") && dash("Node 3: direct"));
  assert(has(data(N2), "\"1\":{\"d\":1,\"v\":0}") && has(data(N1), "\"3\":{\"d\":1,\"v\":0}"));
  ok("links: every node heard directly on a bench");

  // Put Nodes 1 and 3 out of range of each other; they must then reach each other through Node 2.
  web(N2, "/cmd", {{"c", "deaf"}, {"to", "1"}, {"ing", "3"}});
  web(N2, "/cmd", {{"c", "deaf"}, {"to", "3"}, {"ing", "1"}});
  run(4000);                                     // the direct path has to age out (LINK_FORGET_MS)
  assert(has(data(N1), "\"3\":{\"d\":0,\"v\":2}") && has(data(N3), "\"1\":{\"d\":0,\"v\":2}"));
  assert(has(data(N2), "\"1\":{\"d\":1,\"v\":0}") && has(data(N2), "\"3\":{\"d\":1,\"v\":0}"));
  assert(n1::state == n1::NORMAL && n1::peers[1].alive && n3::node1.alive);  // still ALIVE, via the relay
  cupMl = 0; run(1200);
  web(N2, "/cmd", {{"c", "pour"}, {"ing", "0"}, {"ml", "250"}});   // longer than the cup holds
  run(600);
  assert(pinOut[N1][25] == HIGH);
  run(11000);
  assert(!anyRelay() && log2("Node 1: coffee pump OFF - cup full (Node 3)"));  // cross-node stop, relayed
  ok("Nodes 1 and 3 out of range: multi-hop through Node 2, cup-full stop still works");

  nodeUp[N2] = false; run(4000);                 // the relay itself dies: both ends must go SAFE
  assert(n1::state == n1::SAFE && !anyRelay() && n3::view == "SAFE");
  nodeUp[N2] = true; run(2500);
  web(N2, "/cmd", {{"c", "deaf"}, {"to", "1"}, {"ing", "3"}});
  web(N2, "/cmd", {{"c", "deaf"}, {"to", "3"}, {"ing", "1"}});
  run(2000);
  web(N2, "/cmd", {{"c", "ack"}}); run(1000);
  assert(n1::meshDeaf[3] == false && n3::meshDeaf[1] == false);
  assert(n1::state == n1::NORMAL && has(data(N1), "\"3\":{\"d\":1,\"v\":0}"));
  ok("losing the relay trips SAFE; back in range the links read direct again");

  // No message may exceed what one ESP-NOW frame carries.
  size_t biggest = 0;
  for (auto* s : {&n1::webStatus[1], &n2::webStatus[2], &n3::webStatus[3]}) biggest = std::max(biggest, s->size());
  assert(biggest + 12 <= 250 && n1::meshTooBig == 0 && n2::meshTooBig == 0 && n3::meshTooBig == 0);
  assert(n1::meshDropped == 0 && n2::meshDropped == 0 && n3::meshDropped == 0);
  ok("every message fits in one ESP-NOW frame; nothing dropped");

  // ---------- web dashboard ----------
  for (int n : {N1, N2, N3}) {
    std::string page = web(n, "/");
    assert(webOf[n]->headers["Content-Encoding"] == "gzip" && page.size() == DASHBOARD_HTML_GZ_LEN && (unsigned char)page[0] == 31);
    std::string d = data(n);
    assert(has(d, ("{\"me\":" + std::to_string(n + 1)).c_str()));
    assert(has(d, "\"zone\":\"pump station\"") && has(d, "\"zone\":\"control\"") && has(d, "\"zone\":\"output\""));
    assert(has(d, "\"lvl\":[77,77,77]") && has(d, "\"raw\":[1400,1400,1400]") && has(d, "\"cup\":") && has(d, "\"joy\":[1900,1900]"));
    assert(has(d, "\"ip\":\"192.168.4.1\"") && !has(d, "192.168.1"));   // one address on every node
    assert(has(d, "\"links\":{\"1\":{\"d\":") && has(d, "\"radio\":{\"sent\":") && has(d, "\"log\":[{\"t\":"));
    assert(!has(d, "\"age\":-1") && !has(d, "\"s\":null"));
  }
  for (int n : {N1, N2, N3}) {   // any unknown path, e.g. a phone's connectivity probe, goes to the named address
    web(n, "*");
    assert(webOf[n]->code == 302 && webOf[n]->headers["Location"] == "http://barista.io/");
    assert(oledText[n].empty() || oledText[n].find("barista.io") != std::string::npos);
  }
  assert(dnsStarted == 3 && dnsPolled > 1000);
  ok("every node serves the page and the full status of all three nodes");

  cupMl = 0; run(1200);
  web(N3, "/cmd", {{"c", "pour"}, {"ing", "1"}, {"ml", "40"}});   // page on Node 3 -> mesh -> Node 1
  run(300);
  assert(pinOut[N1][26] == HIGH && has(data(N2), "\"pump\":2"));
  std::ofstream("sample_pouring.json") << data(N2);
  web(N2, "/cmd", {{"c", "stop"}});
  run(300);
  assert(!anyRelay() && log3("Node 1: milk pump OFF - stopped from the dashboard"));
  web(N1, "/cmd", {{"c", "pour"}, {"ing", "2"}, {"ml", "20"}});   // page on Node 1 itself
  run(300);
  assert(pinOut[N1][27] == HIGH);
  run(1500);
  assert(!anyRelay() && log2("Node 1: cream pump OFF - pour done"));
  web(N2, "/cmd", {{"c", "pour"}, {"ing", "7"}, {"ml", "20"}});
  web(N2, "/cmd", {{"c", "pour"}, {"ing", "0"}, {"ml", "9999"}});
  run(300);
  assert(!anyRelay() && log2("Node 1: pour refused: bad request"));
  web(N2, "/cmd", {{"c", "x"}});
  assert(webOf[N2]->code == 400);
  ok("dashboard pours and stop work from any node; bad requests are refused");

  quiet();
  web(N3, "/cmd", {{"c", "buzz"}, {"to", "1"}}); run(500);
  assert(buzz1 && !buzz2);
  run(1000); quiet(); run(300);
  assert(!buzz1);                                                // the test beep ends by itself
  web(N1, "/cmd", {{"c", "buzz"}, {"to", "2"}}); run(500);
  assert(buzz2 && !buzz1);
  web(N2, "/cmd", {{"c", "led"}, {"to", "3"}});
  run(300);  assert(led(255, 0, 0));
  run(700);  assert(led(0, 255, 0));
  run(700);  assert(led(0, 0, 255));
  run(700);  assert(led(0, 255, 0) && n3::view == "NORMAL");     // back to green = ready
  ok("buzzer and LED tests reach the right node");

  run(1000); quiet();
  web(N3, "/cmd", {{"c", "trip"}}); run(800);
  assert(n1::state == n1::SAFE && n2::sysState == "SAFE" && n2::affected == "pump station: tripped from the dashboard" && buzz1 && buzz2);
  web(N3, "/cmd", {{"c", "pour"}, {"ing", "0"}, {"ml", "30"}}); run(300);
  assert(!anyRelay() && log3("pour refused: SAFE (tripped from the dashboard)"));
  web(N3, "/cmd", {{"c", "ack"}}); run(800);
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL");
  ok("Trip SAFE and Acknowledge from the dashboard");

  nodeUp[N2] = false;                                            // Node 2 turns off: the page moves to Node 1 / 3
  analogVal[N1][33] = 900;                                       // milk level changes while Node 2 is gone
  run(6500);
  for (int n : {N1, N3}) {
    std::string d = data(n);
    assert(has(d, "\"lvl\":[77,50,77]") && has(d, "\"state\":\"SAFE\"") && has(d, "lost Node 2 (control)"));
    assert(has(d, "Node 2 (control) LOST") && has(d, "\"zone\":\"control\""));   // event log + Node 2's last status
  }
  web(N3, "/cmd", {{"c", "pour"}, {"ing", "0"}, {"ml", "30"}}); run(300);
  assert(!anyRelay() && log3("pour refused: SAFE (lost Node 2 (control))"));
  std::ofstream("sample_n2off_from1.json") << data(N1);
  std::ofstream("sample_n2off_from3.json") << data(N3);
  quiet(); web(N1, "/cmd", {{"c", "led"}, {"to", "3"}}); run(300);
  assert(led(255, 0, 0));
  ok("Node 2 off: SAFE, pours refused, Nodes 1 and 3 still serve status, levels and tests");

  run(2500);
  web(N3, "/cmd", {{"c", "ack"}}); run(500);                     // operator acknowledges from the dashboard
  assert(n1::state == n1::DEGRADED && log1("ACK accepted - running without Node 2") && n3::view == "DEGRADED");
  quiet(); run(700); assert(!buzz1);                             // alarm is silenced
  std::ofstream("sample_n2off_acked.json") << data(N1);
  cupMl = 0; run(1200);
  web(N3, "/cmd", {{"c", "pour"}, {"ing", "0"}, {"ml", "40"}}); run(300);
  assert(pinOut[N1][25] == HIGH);
  run(2200);
  assert(!anyRelay() && log1("coffee pump OFF - pour done"));
  web(N1, "/cmd", {{"c", "pour"}, {"ing", "2"}, {"ml", "290"}}); run(300);
  assert(pinOut[N1][27] == HIGH);
  nodeUp[N3] = false; run(4500);                                 // now the cup node dies too: SAFE, and no way out
  assert(!anyRelay() && n1::state == n1::SAFE);
  web(N1, "/cmd", {{"c", "ack"}}); run(300);
  assert(n1::state == n1::SAFE && log1("ACK rejected: Node 3 still LOST (no cup reading)"));
  nodeUp[N3] = true; run(2500);
  web(N1, "/cmd", {{"c", "ack"}}); run(500);
  assert(n1::state == n1::DEGRADED);
  nodeUp[N2] = true; analogVal[N1][33] = 1400; run(3000);        // Node 2 returns: back to NORMAL without another ACK
  assert(n1::state == n1::NORMAL && n2::sysState == "NORMAL");
  ok("Node 2 off + ACK: runs DEGRADED from the dashboard; losing Node 3 still locks it in SAFE");

  n2::sel = 0; n2::ml = 60;
  pushX(1100); assert(n2::sel == 2);                             // a modest push now counts (800 from rest)
  pushX(1100); assert(n2::sel == 1);
  pushX(2700); assert(n2::sel == 2);
  analogVal[N2][34] = 0; run(500); int stuck = n2::sel; run(2000);
  assert(n2::sel == stuck);                                      // a dead axis moves one step at most, never spins
  analogVal[N2][34] = 1900; run(100);
  ok("joystick: steps relative to its resting value");

  std::cout << "largest status " << biggest << " bytes (limit 250), /data " << data(N2).size()
            << " bytes, " << espNowFrames << " frames sent in the run\n";
  std::ofstream("sample_data.json") << data(N2);
  return 0;
}
