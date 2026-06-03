"""SessionStart hook: ensure the Mirror server is up, then show the user the link.

Reads the hook payload on stdin, starts/reuses the server, and prints JSON with a
``systemMessage`` (shown in the terminal) plus ``additionalContext`` (so the model
can also mention the link).
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
        port = ensure_running(transcript_path, session_id)
    except Exception as exc:  # never break the session over a viewer
        print(json.dumps({"systemMessage": "Mirror could not start: %s" % exc}))
        return

    url = "http://localhost:%d" % port
    print(
        json.dumps(
            {
                "systemMessage": "\U0001FA9E Mirror live view: %s" % url,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "A live HTML mirror of this conversation is available at %s "
                        "(localhost only). Mention this link to the user." % url
                    ),
                },
            }
        )
    )


if __name__ == "__main__":
    main()
