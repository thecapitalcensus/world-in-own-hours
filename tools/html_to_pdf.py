#!/usr/bin/env python3
"""Print an HTML file to a paginated PDF with headless Chrome over the DevTools protocol.

Usage: python3 tools/html_to_pdf.py output/paper/resident.html output/paper/resident.pdf
Adds a footer with the running title and "page / total". Honours the page's @page rule (A4, margins).
Fallback without Chrome: tools/html_to_pdf.swift (system WebKit; weaker page-break control, no footer).
"""
import base64, json, os, socket, subprocess, sys, tempfile, time, urllib.request
import websocket  # pip install --user websocket-client

CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
title = sys.argv[3] if len(sys.argv) > 3 else "The Capital Census · Holding the World in One’s Own Hours · v1.0"

with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
prof = tempfile.mkdtemp(prefix="chrome-pdf-")
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                         f"--remote-debugging-port={port}", f"--user-data-dir={prof}", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")); break
        except Exception:
            time.sleep(0.1)
    page = next(t for t in targets if t["type"] == "page")
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], max_size=None)
    _id = [0]
    def call(method, **params):
        _id[0] += 1; ws.send(json.dumps({"id": _id[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == _id[0]:
                if "error" in m: raise RuntimeError(m["error"])
                return m.get("result", {})
            if m.get("method") == "Page.loadEventFired": loaded[0] = True
    loaded = [False]
    call("Page.enable")
    call("Emulation.setEmulatedMedia", media="print")
    call("Page.navigate", url="file://" + src)
    t0 = time.time()
    while not loaded[0] and time.time() - t0 < 30:
        m = json.loads(ws.recv())
        if m.get("method") == "Page.loadEventFired": loaded[0] = True
    time.sleep(1.0)  # fonts and images
    foot = ('<div style="font-family:-apple-system,Helvetica,Arial,sans-serif;font-size:7pt;color:#777;width:100%;'
            'padding:0 15mm;display:flex;justify-content:space-between;">'
            f'<span>{title}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    r = call("Page.printToPDF", printBackground=True, preferCSSPageSize=True, displayHeaderFooter=True,
             headerTemplate="<div></div>", footerTemplate=foot,
             marginTop=0.51, marginBottom=0.6, marginLeft=0.59, marginRight=0.59,  # inches; overridden by @page except for footer space
             transferMode="ReturnAsBase64")
    data = base64.b64decode(r["data"])
    open(dst, "wb").write(data)
    print(f"wrote {dst} ({len(data)} bytes)")
    ws.close()
finally:
    proc.terminate()
    try: proc.wait(5)
    except Exception: proc.kill()
