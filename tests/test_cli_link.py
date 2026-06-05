import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SERVER_DIR = os.path.join(HERE, "..", "server")
CLI = os.path.join(SERVER_DIR, "cli_link.py")


class TestCliLink(unittest.TestCase):
    def test_prints_url_when_server_not_running(self):
        # active pointer has a port but NO transcript_path, so cli_link reports
        # the URL without trying to spawn a server (keeps the test hermetic).
        tmp = tempfile.mkdtemp(prefix="mirror-cli-")
        with open(os.path.join(tmp, "active.json"), "w") as fh:
            json.dump({"port": 9999}, fh)
        env = dict(os.environ, MIRROR_STATE_DIR=tmp)
        out = subprocess.run(
            [sys.executable, CLI], env=env, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("http://localhost:9999", out.stdout)


if __name__ == "__main__":
    unittest.main()
