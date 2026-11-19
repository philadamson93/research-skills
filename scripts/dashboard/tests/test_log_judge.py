"""A run whose session sleeps on a long job is judged from its own logs (Phil 2026-11-19)."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_dashboard as b  # noqa: E402


class LogJudge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plan = Path(self.tmp.name) / "planning"
        (self.plan / "x" / "logs").mkdir(parents=True)
        self.rb = self.plan / "x" / "readback.md"
        self.rb.write_text("Status: running — training started\n")
        self.log = self.plan / "x" / "logs" / "train.log"

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, **kw):
        run = {"label": "t", "machine": "box", "readback": "planning/x/readback.md", "watch": ["planning/x/logs"],
               "job": "train.py", "quiet_h": 6, **kw}
        return b.run_status(run, self.plan, time.time(), {})

    def test_done_text_in_log_beats_stale_running_readback(self):
        self.log.write_text("epoch 99/100\nepoch 100/100\nTraining complete\n")
        r = self.run_(done_text=r"Training complete", progress=r"epoch \d+/\d+")
        self.assertEqual(r["state"], "done")
        self.assertIn("Training complete", r["summary"])

    def test_traceback_means_failed(self):
        self.log.write_text("epoch 3/100\nTraceback (most recent call last):\n  ...\nCUDA out of memory\n")
        r = self.run_(done_text=r"Training complete", fail_text=r"Traceback|out of memory")
        self.assertEqual(r["state"], "failed")

    def test_progress_shown_while_running(self):
        self.log.write_text("epoch 58/100\nepoch 59/100\n")
        r = self.run_(done_text=r"Training complete", progress=r"epoch \d+/\d+")
        self.assertEqual(r["state"], "running")
        self.assertIn("epoch 59/100", r["summary"])

    def test_done_file_without_any_readback(self):
        (self.plan / "x" / "final.pt").write_text("")
        self.rb.unlink()
        r = self.run_(done_file="planning/x/final.pt")
        self.assertEqual(r["state"], "done")

    def test_no_log_fields_keeps_old_behaviour(self):
        self.log.write_text("Training complete\n")
        self.assertEqual(self.run_()["state"], "running")


if __name__ == "__main__":
    unittest.main()
