"""Stop hook: keep the active pointer fresh (and the server alive) each turn.

Runs silently. The server live-updates by polling the transcript, so this hook
exists for robustness: it re-points the server at the current transcript and
restarts it if it died (e.g. a resumed session where SessionStart did not run).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launcher import ensure_running  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}

    transcript_path = payload.get("transcript_path")
    session_id = payload.get("session_id")

    try:
        ensure_running(transcript_path, session_id)
    except Exception:
        pass  # silent: a viewer hiccup must never block the turn


if __name__ == "__main__":
    main()
