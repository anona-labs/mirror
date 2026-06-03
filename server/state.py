"""Shared state for Mirror: state dir, the active-session pointer, and port logic.

Single-session v1: one ``active.json`` records which transcript the running server
should follow and which port it listens on. Everything lives under ~/.mirror so the
server never writes anywhere near the user's project.
"""

import json
import os
import socket
import urllib.request

STATE_DIR = os.environ.get("MIRROR_STATE_DIR") or os.path.join(
    os.path.expanduser("~"), ".mirror"
)
ACTIVE_PATH = os.path.join(STATE_DIR, "active.json")
LOG_PATH = os.path.join(STATE_DIR, "server.log")
PID_PATH = os.path.join(STATE_DIR, "server.pid")

DEFAULT_PORT = 7842
HEALTH_TOKEN = "mirror-ok"


def ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)
    return STATE_DIR


def read_active():
    try:
        with open(ACTIVE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_active(transcript_path, session_id, port):
    ensure_state_dir()
    data = {
        "transcript_path": transcript_path,
        "session_id": session_id,
        "port": port,
    }
    tmp = ACTIVE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, ACTIVE_PATH)
    return data


def _port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_free_port(start=DEFAULT_PORT, attempts=50):
    for offset in range(attempts):
        port = start + offset
        if _port_is_free(port):
            return port
    raise RuntimeError("no free port found near %d" % start)


def is_mirror_running(port, timeout=0.5):
    """True only if OUR server answers /healthz on this port."""
    url = "http://127.0.0.1:%d/healthz" % port
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace").strip() == HEALTH_TOKEN
    except Exception:
        return False
