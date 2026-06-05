"""Print (and open) the Mirror live-view URL. Backs the /mirror slash command.

Reuses a running server if one is healthy. If the last active session is known
but the server is not answering, it restarts it via launcher.ensure_running.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import state  # noqa: E402
import launcher  # noqa: E402


def main():
    active = state.read_active()
    port = active.get("port") if active else None

    if not (port and state.is_mirror_running(port)):
        if active and active.get("transcript_path"):
            port = launcher.ensure_running(
                active["transcript_path"], active.get("session_id")
            )
        elif port is None:
            port = state.DEFAULT_PORT

    url = "http://localhost:%d" % port
    if state.is_mirror_running(port):
        launcher._open_browser(url)
        print("Mirror live view: %s (opened in your browser)" % url)
    else:
        print("Mirror is not running yet; it starts on the next turn. URL: %s" % url)


if __name__ == "__main__":
    main()
