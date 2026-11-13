// Fake ESP-NOW: a broadcast bus between the three sketches in this one process.
#pragma once
#include "Arduino.h"
#define ESP_OK 0
#define ESP_NOW_MAX_DATA_LEN 250
typedef int esp_err_t;
struct esp_now_peer_info_t { uint8_t peer_addr[6]; int channel; int ifidx; bool encrypt; };
struct esp_now_recv_info_t { uint8_t* src_addr; uint8_t* des_addr; void* rx_ctrl; };

#if ESP_ARDUINO_VERSION_MAJOR >= 3
typedef void (*EspNowCb)(const esp_now_recv_info_t*, const uint8_t*, int);
#else
typedef void (*EspNowCb)(const uint8_t*, const uint8_t*, int);
#endif
inline EspNowCb espNowCb[3] = {nullptr, nullptr, nullptr};
inline bool nodeUp[3] = {true, true, true};
inline int  espNowFrames = 0;
inline std::string espNowLast;

inline esp_err_t esp_now_init() { return ESP_OK; }
inline esp_err_t esp_now_register_recv_cb(EspNowCb cb) { espNowCb[curNode] = cb; return ESP_OK; }
inline esp_err_t esp_now_add_peer(const esp_now_peer_info_t*) { return ESP_OK; }
inline esp_err_t esp_now_send(const uint8_t*, const uint8_t* data, size_t len) {
  if (!nodeUp[curNode]) return -1;
  espNowFrames++;
  espNowLast.assign((const char*)data, len);
  int from = curNode;
  uint8_t mac[6] = {2, 0, 0, 0, 0, (uint8_t)from};
  esp_now_recv_info_t info{mac, nullptr, nullptr};
  for (int j = 0; j < 3; j++) {
    if (j == from || !nodeUp[j] || !espNowCb[j]) continue;
    curNode = j;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
    espNowCb[j](&info, data, (int)len);
#else
    espNowCb[j](mac, data, (int)len);
#endif
  }
  curNode = from;
  return ESP_OK;
}
