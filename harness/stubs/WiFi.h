// Fake WiFi: just enough for the softAP calls barista_mesh.h makes.
#pragma once
#include "Arduino.h"
#define WIFI_AP 2
#define WIFI_IF_AP 1
struct IPAddress {
  int o[4] = {0, 0, 0, 0};
  IPAddress() {}
  IPAddress(int a, int b, int c, int d) : o{a, b, c, d} {}
  String toString() const { return String(o[0]) + "." + o[1] + "." + o[2] + "." + o[3]; }
};
inline IPAddress apIP[3];
struct WiFiStub {
  void mode(int) {}
  bool softAPConfig(IPAddress ip, IPAddress, IPAddress) { apIP[curNode] = ip; return true; }
  bool softAP(const char*, const char*, int) { return true; }
  void setSleep(bool) {}
  IPAddress softAPIP() { return apIP[curNode]; }
};
inline WiFiStub WiFi;
