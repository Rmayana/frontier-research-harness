from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from frontier_research_harness.codex_app_server import CodexAppServer, HostRejected


class CodexAppServerTests(unittest.TestCase):
    def host(self):
        popen = subprocess.Popen
        fixture = Path(__file__).parent / "fixtures" / "fake_native_host.py"
        with patch("frontier_research_harness.codex_app_server.subprocess.Popen", side_effect=lambda args, **kw: popen([sys.executable, "-u", str(fixture)], **kw)):
            return CodexAppServer(timeout=2)

    def test_drains_stderr_and_surfaces_request_without_auto_reply(self):
        with self.host() as host:
            self.assertTrue(host.call("exercise", {})["done"])
            events = host.drain_events()
            self.assertEqual(events[0]["id"], 9)
            self.assertLessEqual(len(host.diagnostics), 100)
            host.respond(9, {"answers": {}})
            host.call("barrier", {})
            self.assertEqual(host.drain_events()[0]["method"], "fixture/response")

    def test_rejection_is_definite_and_eof_interrupts_wait(self):
        with self.host() as host:
            with self.assertRaises(HostRejected): host.call("reject", {})
            before = time.monotonic()
            with self.assertRaises(ConnectionError): host.call("close-now", {})
            self.assertLess(time.monotonic() - before, 1.5)
            self.assertEqual(host.drain_events()[-1]["method"], "transport/closed")


if __name__ == "__main__": unittest.main()
