#pragma once
#include "WiFi.h"
inline int dnsStarted = 0, dnsPolled = 0;
struct DNSServer {
  bool start(int port, const char* name, IPAddress) { if (port == 53 && name[0] == '*') dnsStarted++; return true; }
  void processNextRequest() { dnsPolled++; }
};
