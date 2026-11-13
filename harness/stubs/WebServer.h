// Fake WebServer: the test calls a node's handlers directly and reads back what they sent.
#pragma once
#include "Arduino.h"
#include <functional>
#include <map>
struct WebServer;
inline WebServer* webOf[3];
struct WebServer {
  std::map<std::string, std::function<void()>> routes;
  std::map<std::string, std::string> args, headers;
  int code = 0; std::string type, body;
  WebServer(int) {}
  void on(const char* path, void (*h)()) { routes[path] = h; }
  void onNotFound(std::function<void()> h) { routes["*"] = h; }
  void sendHeader(const char* k, const std::string& v) { headers[k] = v; }
  void begin() { webOf[curNode] = this; }
  void handleClient() {}
  String arg(const char* k) { return String(args.count(k) ? args[k] : ""); }
  void sendHeader(const char* k, const char* v) { headers[k] = v; }
  void send(int c, const char* t, const std::string& b) { code = c; type = t; body = b; }
  void send_P(int c, const char* t, const char* b, size_t n) { code = c; type = t; body.assign(b, n); }
};
