// Small stand-in for ArduinoJson: the v6/v7-compatible calls the three sketches use.
#pragma once
#include <utility>
#include <vector>

struct JVal {
  int t = 0;  // 0 null, 1 number, 2 string, 3 object, 4 bool, 5 array
  double n = 0; std::string s;
  std::vector<std::pair<std::string, JVal>> o; std::vector<JVal> a;
  JVal* find(const std::string& k) { for (auto& kv : o) if (kv.first == k) return &kv.second; return nullptr; }
};

struct JsonArrayConst; struct JsonObjectConst;
struct JsonVariantConst {
  const JVal* v = nullptr;
  bool isNull() const { return !v || v->t == 0; }
  int operator|(int d) const { return v && v->t == 1 ? (int)v->n : d; }
  unsigned operator|(unsigned d) const { return v && v->t == 1 ? (unsigned)v->n : d; }
  float operator|(float d) const { return v && v->t == 1 ? (float)v->n : d; }
  const char* operator|(const char* d) const { return v && v->t == 2 ? v->s.c_str() : d; }
  JsonVariantConst operator[](int i) const { return {v && v->t == 5 && i < (int)v->a.size() ? &v->a[i] : nullptr}; }
  JsonVariantConst operator[](const char* k) const { return {v && v->t == 3 ? const_cast<JVal*>(v)->find(k) : nullptr}; }
  template <class T> T as() const;
};
struct JsonArrayConst {
  const JVal* v = nullptr;
  struct It {
    const JVal* p;
    JsonVariantConst operator*() const { return {p}; }
    It& operator++() { ++p; return *this; }
    bool operator!=(const It& o) const { return p != o.p; }
  };
  It begin() const { return {v && v->t == 5 ? v->a.data() : nullptr}; }
  It end() const { return {v && v->t == 5 ? v->a.data() + v->a.size() : nullptr}; }
};
struct JsonObjectConst {
  const JVal* v = nullptr;
  JsonVariantConst operator[](const char* k) const { return JsonVariantConst{v}[k]; }
};
template <class T> T JsonVariantConst::as() const {
  if constexpr (std::is_same_v<T, const char*>) return v && v->t == 2 ? v->s.c_str() : nullptr;
  else if constexpr (std::is_same_v<T, int>) return v && v->t == 1 ? (int)v->n : 0;
  else return T{v};  // JsonArrayConst / JsonObjectConst
}

struct JsonArray {
  JVal* v;
  void add(int x) { JVal e; e.t = 1; e.n = x; v->a.push_back(e); }
};
struct JProxy {
  JVal* root; std::string k;
  JVal& slot() { if (auto p = root->find(k)) return *p; root->o.push_back({k, {}}); return root->o.back().second; }
  JsonVariantConst get() const { return {root->find(k)}; }
  void operator=(int d) { auto& s = slot(); s.t = 1; s.n = d; }
  void operator=(unsigned d) { auto& s = slot(); s.t = 1; s.n = d; }
  void operator=(unsigned long d) { auto& s = slot(); s.t = 1; s.n = (double)d; }
  void operator=(float d) { auto& s = slot(); s.t = 1; s.n = d; }
  void operator=(const char* c) { auto& s = slot(); s.t = 2; s.s = c; }
  void operator=(const std::string& c) { operator=(c.c_str()); }
  template <class T> auto operator|(T d) const { return get() | d; }
  bool isNull() const { return get().isNull(); }
  template <class T> T as() const { return get().template as<T>(); }
  JsonVariantConst operator[](int i) const { return get()[i]; }
};
struct JsonDocument {
  JVal root;
  JsonDocument() { root.t = 3; }
  JProxy operator[](const char* k) { return {&root, k}; }
  JsonArray createNestedArray(const char* k) { JProxy p{&root, k}; auto& s = p.slot(); s.t = 5; return {&s}; }
  template <class T> T as() const { return T{&root}; }
};
struct DynamicJsonDocument : JsonDocument { DynamicJsonDocument(size_t) {} };

struct JParser {
  const char* p; bool err = false;
  void ws() { while (*p == ' ' || *p == '\n' || *p == '\t' || *p == '\r') p++; }
  std::string str() { std::string r; p++; while (*p && *p != '"') r += *p++; if (*p != '"') err = true; else p++; return r; }
  JVal val() {
    ws(); JVal v;
    if (*p == '{') {
      v.t = 3; p++; ws();
      if (*p == '}') { p++; return v; }
      while (!err) {
        ws(); if (*p != '"') { err = true; break; }
        std::string k = str(); ws(); if (*p != ':') { err = true; break; } p++;
        v.o.push_back({k, val()}); ws();
        if (*p == ',') { p++; continue; }
        if (*p == '}') { p++; break; }
        err = true;
      }
    } else if (*p == '[') {
      v.t = 5; p++; ws();
      if (*p == ']') { p++; return v; }
      while (!err) {
        v.a.push_back(val()); ws();
        if (*p == ',') { p++; continue; }
        if (*p == ']') { p++; break; }
        err = true;
      }
    } else if (*p == '"') { v.t = 2; v.s = str(); }
    else if (!strncmp(p, "true", 4)) { v.t = 4; v.n = 1; p += 4; }
    else if (!strncmp(p, "false", 5)) { v.t = 4; p += 5; }
    else { char* e; v.n = strtod(p, &e); if (e == p) err = true; else { v.t = 1; p = e; } }
    return v;
  }
};
inline bool deserializeJson(JsonDocument& d, const std::string& s) {
  JParser ps{s.c_str()}; ps.ws();
  if (*ps.p != '{') return true;
  d.root = ps.val();
  return ps.err;
}
inline void jser(const JVal& v, std::string& out) {
  if (v.t == 1) { char b[32]; snprintf(b, sizeof b, "%.10g", v.n); out += b; }
  else if (v.t == 2) out += "\"" + v.s + "\"";
  else if (v.t == 3) {
    out += "{";
    for (size_t i = 0; i < v.o.size(); i++) { if (i) out += ","; out += "\"" + v.o[i].first + "\":"; jser(v.o[i].second, out); }
    out += "}";
  } else if (v.t == 5) {
    out += "[";
    for (size_t i = 0; i < v.a.size(); i++) { if (i) out += ","; jser(v.a[i], out); }
    out += "]";
  } else out += "null";
}
inline void serializeJson(JsonDocument& d, std::string& out) { out.clear(); jser(d.root, out); }
