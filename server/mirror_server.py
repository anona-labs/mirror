"""Mirror local server: serves the client and the parsed conversation, live.

Stdlib only. Binds to 127.0.0.1 exclusively (the transcript can contain secrets,
file contents, and tool output, so it never leaves the machine in v1).

Routes:
  GET /                 -> client/index.html
  GET /app.js /style.css /vendor/* -> static client assets (no path traversal)
  GET /healthz          -> "mirror-ok" (used by the hook to detect our server)
  GET /api/conversation -> {"items": [...], "version": "<mtime>-<size>"}
  GET /events           -> Server-Sent Events; emits on transcript change
"""

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import state  # noqa: E402
from parser import parse_transcript  # noqa: E402

CLIENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client")

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}

# Only these client files may be served. Keeps path traversal impossible.
ALLOWED_STATIC = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
    "/vendor/marked.min.js": "vendor/marked.min.js",
    "/vendor/highlight.min.js": "vendor/highlight.min.js",
    "/vendor/highlight-github-dark.min.css": "vendor/highlight-github-dark.min.css",
}


def _transcript_version(path):
    try:
        st = os.stat(path)
        return "%d-%d" % (int(st.st_mtime * 1000), st.st_size)
    except OSError:
        return "none"


def _active_transcript():
    active = state.read_active()
    if not active:
        return None
    return active.get("transcript_path")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the server log quiet; errors still surface via exceptions

    def _send(self, code, body, content_type, extra_headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self._send(200, state.HEALTH_TOKEN, "text/plain; charset=utf-8")
        if path == "/api/conversation":
            return self._serve_conversation()
        if path == "/events":
            return self._serve_events()
        if path in ALLOWED_STATIC:
            return self._serve_static(ALLOWED_STATIC[path])
        return self._send(404, "not found", "text/plain; charset=utf-8")

    def _serve_static(self, rel):
        full = os.path.join(CLIENT_DIR, rel)
        if not os.path.isfile(full):
            return self._send(404, "missing: %s" % rel, "text/plain; charset=utf-8")
        ext = os.path.splitext(full)[1]
        ctype = STATIC_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as fh:
            body = fh.read()
        self._send(200, body, ctype)

    def _serve_conversation(self):
        transcript = _active_transcript()
        if not transcript or not os.path.isfile(transcript):
            payload = {"items": [], "version": "none", "waiting": True}
        else:
            payload = parse_transcript(transcript)
            payload["version"] = _transcript_version(transcript)
        self._send(
            200,
            json.dumps(payload),
            "application/json; charset=utf-8",
            {"Cache-Control": "no-store"},
        )

    def _serve_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_version = None
        last_beat = time.time()
        try:
            while True:
                transcript = _active_transcript()
                version = _transcript_version(transcript) if transcript else "none"
                now = time.time()
                if version != last_version:
                    last_version = version
                    self.wfile.write(("data: %s\n\n" % version).encode("utf-8"))
                    self.wfile.flush()
                    last_beat = now
                elif now - last_beat > 15:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    last_beat = now
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=state.DEFAULT_PORT)
    args = ap.parse_args()

    state.ensure_state_dir()
    with open(state.PID_PATH, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    httpd.daemon_threads = True
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
