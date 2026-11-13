// Host stub of the Arduino core for running three sketches in one process. curNode selects whose
// pins and Serial are in use (0 = Node 1, 1 = Node 2, 2 = Node 3).
#pragma once
#include <string>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstdarg>
#include <algorithm>
using std::min;
using std::max;

#ifndef ESP_ARDUINO_VERSION_MAJOR
#define ESP_ARDUINO_VERSION_MAJOR 3   // override with -D to compile the core 2.x callback shape
#endif
#define PROGMEM
#define OUTPUT 1
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0
#define constrain(x, a, b) ((x) < (a) ? (a) : ((x) > (b) ? (b) : (x)))

inline int curNode = 0;
inline unsigned long fakeMillis = 0;
inline int pinOut[3][40];   // digitalWrite / analogWrite values
inline int pinIn[3][40];    // digitalRead values
inline int analogVal[3][40];
inline unsigned long millis() { return fakeMillis; }
inline void pinMode(int, int) {}
inline void digitalWrite(int p, int v) { pinOut[curNode][p] = v; }
inline void analogWrite(int p, int v) { pinOut[curNode][p] = v; }
inline int digitalRead(int p) { return pinIn[curNode][p]; }
inline int analogRead(int p) { return analogVal[curNode][p]; }
inline long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }

struct String : std::string {
  String() {}
  String(const char* s) : std::string(s ? s : "") {}
  String(const std::string& s) : std::string(s) {}
  String(char c) : std::string(1, c) {}
  String(int v) : std::string(std::to_string(v)) {}
  String(unsigned v) : std::string(std::to_string(v)) {}
  String(long v) : std::string(std::to_string(v)) {}
  String(unsigned long v) : std::string(std::to_string(v)) {}
  String(double v, int dec = 2) { char b[32]; snprintf(b, sizeof b, "%.*f", dec, v); assign(b); }
  String(float v, int dec = 2) : String((double)v, dec) {}
  int toInt() const { return atoi(c_str()); }
  float toFloat() const { return (float)atof(c_str()); }
};
template <class T> String operator+(const String& a, const T& b) { String r(a); r.append(String(b)); return r; }
inline String operator+(const String& a, const char* b) { String r(a); r.append(b); return r; }
inline String operator+(const char* a, const String& b) { String r(a); r.append(b); return r; }

inline std::string serialOut[3];
struct SerialStub {
  void begin(int) {}
  void println() { serialOut[curNode] += "\n"; }
  void print(const std::string& s) { serialOut[curNode] += s; }
  void println(const std::string& s) { serialOut[curNode] += s + "\n"; }
  void printf(const char* f, ...) {
    char b[1024]; va_list ap; va_start(ap, f); vsnprintf(b, sizeof b, f, ap); va_end(ap); serialOut[curNode] += b;
  }
};
inline SerialStub Serial;
