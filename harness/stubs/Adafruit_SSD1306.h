// No-op OLED that records the text of the last frame per node.
#pragma once
#include "Arduino.h"
#include "Wire.h"
#define SSD1306_SWITCHCAPVCC 2
#define SSD1306_WHITE 1
inline std::string oledText[3];
struct Adafruit_SSD1306 {
  Adafruit_SSD1306(int, int, TwoWire*, int) {}
  bool begin(int, int) { return true; }
  void clearDisplay() { oledText[curNode].clear(); }
  void setTextColor(int) {}
  void setTextSize(int) {}
  void setCursor(int, int) {}
  template <class T> void print(const T& v) { oledText[curNode] += String(v); }
  template <class T> void println(const T& v) { oledText[curNode] += String(v) + "\n"; }
  void display() {}
};
