"""Loads the dashboard in headless Chrome against three fake nodes (127.0.0.1-3, port 80) that answer
with /data captured from the firmware simulation, then turns "Node 2" off to check the fail-over."""
import gzip, json, os, re, threading, time, copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
T = HERE + "/"
hdr = open(f"{ROOT}/node2_control_center/dashboard_html.h").read()
GZ = bytes(int(x) for x in re.findall(r"\d+", hdr[hdr.index("{"):hdr.index("};")]))
assert gzip.decompress(GZ) == open(f"{ROOT}/dashboard_src/dashboard.html", "rb").read()
assert int(re.search(r"GZ_LEN = (\d+)", hdr).group(1)) == len(GZ)

IP = {1: "127.0.0.1", 2: "127.0.0.2", 3: "127.0.0.3"}
HOST = "127.0.0.2"   # stands in for 192.168.4.1: one address, answered by whichever node the device is joined to
start = time.time()
DIRECT = {"1": {"d": 1, "v": 0}, "2": {"d": 1, "v": 0}, "3": {"d": 1, "v": 0}}
state = {"sample": {1: "sample_data", 2: "sample_data", 3: "sample_data"}, "up": {1: True, 2: True, 3: True},
         "links": {n: copy.deepcopy(DIRECT) for n in IP}, "extra": [], "cmds": [], "who": 2}

def payload(node):
    d = copy.deepcopy(json.load(open(T + state["sample"][node] + ".json")))
    shift = int((time.time() - start) * 1000) + 100000 - d["now"]     # the node's clock keeps running
    d["me"], d["now"] = node, d["now"] + shift
    for n, x in d["nodes"].items():
        if x["s"]: x["s"]["ip"] = HOST   # every node has the same address; here that is the test host
    for e in d["log"]: e["t"] += shift
    d["log"] += state["extra"]
    d["links"] = state["links"][node]
    return json.dumps(d).encode()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, ctype, body, gz=False):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        if gz: self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def node(self): return state["who"] if self.server.server_address[0] == HOST else int(self.server.server_address[0][-1])
    def do_GET(self):
        n = self.node()
        if not state["up"][n]: time.sleep(5); return               # a dead node: no answer
        if self.path == "/": self.reply(200, "text/html", GZ, True)
        elif self.path == "/data": self.reply(200, "application/json", payload(n))
        else: self.reply(404, "text/plain", b"")
    def do_POST(self):
        n = self.node()
        if not state["up"][n]: time.sleep(5); return
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        state["cmds"].append((n, {k: v[0] for k, v in parse_qs(body).items()}))
        self.reply(200, "text/plain", b"sent")

for n in IP:
    threading.Thread(target=ThreadingHTTPServer((IP[n], 80), H).serve_forever, daemon=True).start()

def ok(name): print("ok ", name, flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    errors = []
    def page_for(w, h, scheme):
        pg = b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text
              and "ERR_" not in m.text and "file:///data" not in m.text else None)
        return pg

    pg = page_for(1200, 1500, "light")
    pg.goto("http://127.0.0.2/")
    pg.wait_for_function("document.querySelector('#state').textContent==='NORMAL'")
    t = pg.inner_text("body")
    assert "All zones OK" in t and "Node 2, control" in pg.inner_text("#served") and pg.inner_text("#ip") == "127.0.0.2"
    assert pg.inner_text("#lv0") == "77%" and pg.inner_text("#lv3") == "31%" and pg.inner_text("#sub0") == "Pump ready"
    assert pg.locator("#nodewrap .pill.ok").count() == 3
    assert "this page" in pg.locator("#nodewrap tr").nth(2).inner_text()
    assert pg.locator("#paths li").count() == 2 and pg.locator("#paths .pill.ok").count() == 2
    assert "Node 2 › Node 1" in pg.inner_text("#paths") and "Node 2 › Node 3" in pg.inner_text("#paths")
    assert pg.locator("#feed li").count() == 16 and pg.is_hidden("#demobar") and pg.is_hidden("#lostbar") and pg.is_hidden("#failbar")
    assert pg.is_hidden("#livebtns")
    pg.screenshot(path=T + "shots/shot_live_light.png", full_page=True)
    ok("served gzipped from the header, renders live data from the firmware's /data")

    state["sample"][2] = "sample_pouring"
    pg.wait_for_function("document.querySelector('#pumpnow').textContent==='milk pump running'")
    assert pg.is_visible("#stopbtn") and pg.is_hidden("#ackbtn") and pg.inner_text("#sub1") == "Pouring now"
    pg.click("#stopbtn")
    pg.wait_for_function("document.querySelector('#toasts').textContent.includes('Stop: sent')")
    assert state["cmds"][-1] == (2, {"c": "stop"})
    state["sample"][2] = "sample_data"
    ok("pouring state and Stop button")

    pg.click("text=Test")
    pg.click("text=Beep Node 1 buzzer"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (2, {"c": "buzz", "to": "1"})
    pg.click("text=Cycle Node 3 LED"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (2, {"c": "led", "to": "3"})
    pg.click("text=Milk pump, 10 mL"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (2, {"c": "pour", "ing": "1", "ml": "10"})
    pg.select_option("#pouring", "2"); pg.fill("#pourml", "80"); pg.click("#pourbtn"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (2, {"c": "pour", "ing": "2", "ml": "80"})
    n = len(state["cmds"]); pg.fill("#pourml", "900"); pg.click("#pourbtn"); pg.wait_for_timeout(300)
    assert len(state["cmds"]) == n and "10 to 300 mL" in pg.inner_text("#toasts")
    pg.click("text=Trip SAFE"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (2, {"c": "trip"})
    assert "every node is heard directly" in pg.inner_text("#rangelbl").lower()
    pg.click("#splitbtn"); pg.wait_for_timeout(500)
    assert state["cmds"][-2:] == [(2, {"c": "deaf", "to": "1", "ing": "3"}), (2, {"c": "deaf", "to": "3", "ing": "1"})]
    # the nodes now report the relayed path; Node 2 still hears both directly
    state["links"][1] = {"1": {"d": 0, "v": 0}, "2": {"d": 1, "v": 0}, "3": {"d": 0, "v": 2}}
    state["links"][3] = {"1": {"d": 0, "v": 2}, "2": {"d": 1, "v": 0}, "3": {"d": 0, "v": 0}}
    assert "1400 (77%)" in pg.inner_text("#inputs") and "milk, 60 mL" in pg.inner_text("#inputs")
    state["extra"] = [{"t": int((time.time() - start) * 1000) + 100000, "m": "Node 1: pour refused: cup full"}]
    pg.wait_for_function("document.querySelector('#toasts .toast.err') && document.querySelector('#toasts').textContent.includes('pour refused: cup full')")
    pg.screenshot(path=T + "shots/shot_test_light.png", full_page=True)
    ok("Test tab sends the right commands; a refused pour shows as a red toast")

    pg.click("text=System")
    assert "Node 2, control" in pg.inner_text("#sysgrid") and '"me": 2' in pg.inner_text("#raw")
    sysg = pg.inner_text("#sysgrid")
    assert "RELAYED BY NODE 2" in sysg.upper() and "NODE 2 IGNORES\nnobody" in sysg.upper().replace("NOBODY", "nobody")
    assert pg.evaluate("bases.length") == 1
    pg.click("text=Live")

    # Node 2 turns off. The device hops to Node 1's Wi-Fi: same address, a different node answers.
    state["up"][2] = False; state["extra"] = []
    pg.wait_for_function("!document.querySelector('#lostbar').hidden", timeout=15000)
    state["who"] = 1; state["up"][1] = True; state["sample"][1] = "sample_n2off_from1"
    state["links"][1] = {"1": {"d": 0, "v": 0}, "2": {"d": 0, "v": 0}, "3": {"d": 1, "v": 0}}
    state["up"][2] = True                                            # the host answers again, now as Node 1
    pg.wait_for_function("document.querySelector('#served').textContent.startsWith('Node 1')", timeout=30000)
    pg.wait_for_function("document.querySelector('#state').textContent==='SAFE'")
    assert "Affected zone: control (Node 2) LOST" in pg.inner_text("#statepill")
    assert pg.is_visible("#failbar") and "Now reading from Node 1" in pg.inner_text("#failbar") and pg.is_hidden("#lostbar")
    assert pg.inner_text("#lv1") == "50%"
    rows = pg.locator("#nodewrap tr")
    assert "LOST" in rows.nth(2).inner_text() and "ALIVE" in rows.nth(1).inner_text() and "ALIVE" in rows.nth(3).inner_text()
    assert pg.is_visible("#ackbtn") and "no path" in pg.inner_text("#paths")
    pg.screenshot(path=T + "shots/shot_failover_light.png", full_page=True)
    pg.click("#ackbtn"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (1, {"c": "ack"})
    state["sample"][1] = "sample_n2off_acked"
    pg.wait_for_function("document.querySelector('#state').textContent==='DEGRADED'")
    assert "running without it" in pg.inner_text("#statepill") and pg.is_hidden("#ackbtn")
    pg.click("text=Test")
    assert pg.is_disabled("text=Beep Node 2 buzzer") and pg.is_enabled("text=Beep Node 1 buzzer") and pg.is_enabled("#pourbtn")
    pg.click("text=Milk pump, 10 mL"); pg.wait_for_timeout(300)
    assert state["cmds"][-1] == (1, {"c": "pour", "ing": "1", "ml": "10"})
    pg.screenshot(path=T + "shots/shot_degraded_test.png", full_page=True)
    ok("Node 2 off: same address answers from Node 1, SAFE then DEGRADED after ACK, pours work")

    state["sample"][1] = "sample_data"; state["links"][1] = copy.deepcopy(DIRECT)
    pg.click("text=Live")
    pg.wait_for_function("document.querySelector('#state').textContent==='NORMAL'")
    assert pg.locator("#nodewrap .pill.ok").count() == 3
    ok("recovery shows NORMAL again")

    dark = page_for(1200, 1500, "dark"); dark.goto("http://127.0.0.2/")
    dark.wait_for_function("document.querySelector('#state').textContent==='NORMAL'")
    dark.screenshot(path=T + "shots/shot_live_dark.png", full_page=True)
    phone = page_for(390, 800, "dark"); phone.goto("http://127.0.0.2/")
    phone.wait_for_function("document.querySelector('#state').textContent==='NORMAL'")
    assert phone.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
    phone.screenshot(path=T + "shots/shot_phone_dark.png", full_page=True)
    phone.click("text=Test"); phone.screenshot(path=T + "shots/shot_phone_test.png", full_page=True)
    assert phone.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
    ok("dark theme and phone width, no sideways scroll")

    demo = page_for(1200, 1300, "light"); demo.goto("file://" + ROOT + "/dashboard_src/dashboard.html")
    demo.wait_for_function("!document.querySelector('#demobar').hidden")
    demo.wait_for_function("document.querySelector('#state').textContent==='NORMAL'")
    demo.click("text=Test"); demo.click("text=Beep Node 1 buzzer")
    assert "demo data" in demo.inner_text("#toasts")
    demo.screenshot(path=T + "shots/shot_demo.png", full_page=True)
    ok("opened as a file: demo data with a banner, commands refused")

    assert not errors, errors
    ok("no script errors")
    b.close()
