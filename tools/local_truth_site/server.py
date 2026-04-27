#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import time


PORT = 9999


POLICY_TEXT = """
Privacy Policy

This local test website is a deterministic consent-behavior fixture.
It collects strictly necessary cookies before consent. It loads analytics only
after explicit accept, except on deliberately bad test pages. Users may reject
all non-essential tracking. The reject choice prevents analytics requests.
The accept choice enables analytics requests and an analytics cookie.

Data categories: device data, usage data, page view events.
Third parties: Deterministic Test Tracker, used only on accept or bad pages.
Retention: analytics events are deleted after 30 days.
User rights: access, deletion, correction, objection, portability.
Contact: dpo@example.test.

""" * 40


def html_page(body: str) -> bytes:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Deterministic Consent Test Site</title>
  <style>
    body {{ font-family: sans-serif; margin: 40px; }}
    #banner {{
      position: fixed;
      bottom: 20px;
      left: 20px;
      right: 20px;
      padding: 20px;
      border: 2px solid #333;
      background: #fff9d6;
      z-index: 9999;
    }}
    button {{ margin: 6px; padding: 8px 12px; }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
{body}
</body>
</html>""".encode("utf-8")


def base_script(mode: str) -> str:
    fake_click_mode = mode == "fake-click"
    return f"""
<script>
function setCookie(name, value) {{
  document.cookie = name + "=" + value + "; path=/; SameSite=Lax";
}}

function loadTracker(label) {{
  const img = new Image();
  img.src = "http://tracker.test:{PORT}/collect?label=" + encodeURIComponent(label) + "&t=" + Date.now();
  document.body.appendChild(img);
}}

function hideBanner() {{
  const b = document.getElementById("banner");
  if (b) b.style.display = "none";
}}

setCookie("essential_cookie", "1");
localStorage.setItem("essential_storage", "1");

const MODE = "{mode}";
const FAKE_CLICK_MODE = {str(fake_click_mode).lower()};

if (MODE === "preconsent") {{
  loadTracker("preconsent_s0");
}}

function rejectAll() {{
  if (FAKE_CLICK_MODE) return;
  setCookie("consent_status", "reject");
  localStorage.setItem("consent_status", "reject");
  sessionStorage.setItem("consent_status", "reject");
  hideBanner();

  if (MODE === "bad-reject") {{
    setCookie("analytics_cookie", "bad_reject_loaded");
    loadTracker("bad_reject_s1");
  }}
}}

function acceptAll() {{
  if (FAKE_CLICK_MODE) return;
  setCookie("consent_status", "accept");
  setCookie("analytics_cookie", "enabled");
  localStorage.setItem("consent_status", "accept");
  sessionStorage.setItem("consent_status", "accept");
  hideBanner();
  loadTracker("accept_s2");
}}

function openManage() {{
  document.getElementById("manage-panel").classList.remove("hidden");
}}
</script>
"""


def banner(mode: str, manage_only: bool = False) -> str:
    if manage_only:
        buttons = """
          <button id="manage" onclick="openManage()">Manage choices</button>
          <div id="manage-panel" class="hidden">
            <button id="reject" onclick="rejectAll()">Reject All</button>
            <button id="accept" onclick="acceptAll()">Accept All</button>
          </div>
        """
    else:
        buttons = """
          <button id="reject" onclick="rejectAll()">Reject All</button>
          <button id="accept" onclick="acceptAll()">Accept All</button>
          <button id="manage" onclick="openManage()">Manage choices</button>
          <div id="manage-panel" class="hidden">
            <button id="reject2" onclick="rejectAll()">Reject all optional cookies</button>
            <button id="accept2" onclick="acceptAll()">Accept all cookies</button>
          </div>
        """

    return f"""
<h1>Deterministic Consent Test: {mode}</h1>
<p><a href="/privacy">Privacy Policy</a></p>
<p>This page is a deterministic fixture for S0/S1/S2 consent crawling.</p>

<div id="banner">
  <strong>Cookie consent banner</strong>
  <p>Choose whether to allow analytics tracking.</p>
  {buttons}
</div>

{base_script(mode)}
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status=200, content=b"", content_type="text/html"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        host = self.headers.get("Host", "")
        print(f"[{time.strftime('%H:%M:%S')}] {host} {self.path} - " + fmt % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        host = self.headers.get("Host", "")

        # Fake tracker host.
        if host.startswith("tracker.test"):
            if path == "/collect":
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            self._send(404, b"tracker not found", "text/plain")
            return

        # Fake first-party site.
        if path in ["/", "/effective"]:
            self._send(200, html_page(banner("effective")))
            return

        if path == "/bad-reject":
            self._send(200, html_page(banner("bad-reject")))
            return

        if path == "/preconsent":
            self._send(200, html_page(banner("preconsent")))
            return

        if path == "/manage-only":
            self._send(200, html_page(banner("manage-only", manage_only=True)))
            return

        if path == "/fake-click":
          body = f"""
    <h1>Fake Click Page</h1>
    <p><a href="/privacy">Privacy Policy</a></p>
    <p>This page has visible consent buttons that intentionally do nothing.</p>

    <div id="banner">
      <strong>Cookie consent banner</strong>
      <p>Choose whether to allow analytics tracking.</p>
      <button id="reject" onclick="rejectAll()">Reject All</button>
      <button id="accept" onclick="acceptAll()">Accept All</button>
    </div>

    {base_script("fake-click")}
    """
          self._send(200, html_page(body))
          return

        if path == "/no-banner":
            body = f"""
<h1>No Banner Page</h1>
<p><a href="/privacy">Privacy Policy</a></p>
<p>No consent banner exists on this page.</p>
{base_script("no-banner")}
"""
            self._send(200, html_page(body))
            return

        if path == "/blocked":
            body = """
<h1>Access blocked</h1>
<p>recaptcha required</p>
<p>login required</p>
<form><input type="password" placeholder="password"></form>
"""
            self._send(200, html_page(body))
            return

        if path == "/privacy":
            self._send(200, html_page(f"<pre>{POLICY_TEXT}</pre>"))
            return

        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return

        self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    print(f"Serving truth site on http://truthsite.test:{PORT}")
    print(f"Serving fake tracker on http://tracker.test:{PORT}/collect")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
