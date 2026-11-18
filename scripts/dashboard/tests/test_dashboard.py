"""Tests for the work dashboard's judgement rules. Stdlib only:

    python3 -m unittest discover -s scripts/dashboard/tests -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_dashboard as b  # noqa: E402
import pages  # noqa: E402


def host(name, procs=(), stale=False):
    return {"host": name, "stale": stale, "machine": {"jobs": [], "procs": list(procs)}}


class StatusLine(unittest.TestCase):
    def parse(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(text)
        try:
            return b.readback_status(Path(f.name))
        finally:
            os.unlink(f.name)

    def test_documented_forms(self):
        self.assertEqual(self.parse("Reference: x\nProgram: y\n\nStatus: running — scoring 3 of 9\n")[0], "running")
        self.assertEqual(self.parse("Status: waiting on Phil — go for the $9 run\n"), ("waiting on phil", "go for the $9 run"))
        self.assertEqual(self.parse("**Status:** done - 862 answers, 0 failed\n")[0], "done")
        self.assertEqual(self.parse("Status: FAILED: out of memory\n")[0], "failed")

    def test_absent_or_too_late_is_none(self):
        self.assertIsNone(self.parse("# Readback\nNo status line here.\n")[0])
        self.assertIsNone(self.parse("\n" * 20 + "Status: done — late\n")[0])   # only the top 15 lines count
        self.assertIsNone(self.parse("Status: finished — not a documented word\n")[0])


class RunStates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plan = Path(self.tmp.name) / "planning"
        (self.plan / "x").mkdir(parents=True)
        self.rb = self.plan / "x" / "rb.md"

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, status_line, age_h=0.0, job="train.py", hosts=None, readback="planning/x/rb.md"):
        self.rb.write_text(status_line + "\n")
        t = time.time() - age_h * 3600
        os.utime(self.rb, (t, t))
        run = {"label": "r", "machine": "box", "readback": readback, "job": job, "quiet_h": 6}
        return b.run_status(run, self.plan, time.time(), hosts if hosts is not None else {"box": host("box", ["python3 train.py --x"])})["state"]

    def test_running_recent(self):
        self.assertEqual(self.state("Status: running — x"), "running")

    def test_quiet_but_job_alive_is_not_an_alarm(self):
        self.assertEqual(self.state("Status: running — x", age_h=9), "running, job alive")

    def test_quiet_and_job_gone_is_possibly_died(self):
        self.assertEqual(self.state("Status: running — x", age_h=9, hosts={"box": host("box", ["python3 other.py"])}), "possibly died")

    def test_quiet_with_no_job_name_cannot_check(self):
        self.assertEqual(self.state("Status: running — x", age_h=9, job=""), "quiet, can't check the job")

    def test_quiet_on_machine_not_reporting_cannot_check(self):
        self.assertEqual(self.state("Status: running — x", age_h=9, hosts={}), "quiet, can't check the job")
        self.assertEqual(self.state("Status: running — x", age_h=9, hosts={"box": host("box", ["train.py"], stale=True)}), "quiet, can't check the job")

    def test_other_states(self):
        self.assertEqual(self.state("Status: waiting on Phil — go?"), "waiting on Phil")
        self.assertEqual(self.state("Status: done — ok", age_h=99), "done")
        self.assertEqual(self.state("Status: failed — oom"), "failed")
        self.assertEqual(self.state("no line"), "status unknown")

    def test_readback_paths(self):
        self.assertEqual(self.state("Status: done — x", readback="docs/session/rb.md"), "readback not on the mount")
        self.assertEqual(self.state("Status: done — x", readback="planning/x/missing.md"), "no readback yet")


class Attach(unittest.TestCase):
    items = [{"id": "alpha", "match": ["alpha-run"]}, {"id": "beta", "match": ["beta", "alpha-run-extra"]},
             {"id": "tie1", "match": ["shared-key"]}, {"id": "tie2", "match": ["shared-key"]}]
    ids = {i["id"] for i in items}

    def at(self, **s):
        return b.attach(s, self.items, self.ids, Path("/nonexistent"))

    def test_named_item_wins(self):
        self.assertEqual(self.at(name="alpha-run", parsed={"item": "beta"}), "beta")

    def test_most_specific_match(self):
        self.assertEqual(self.at(name="alpha-run-extra session"), "beta")
        self.assertEqual(self.at(name="alpha-run session"), "alpha")

    def test_ask_beats_folder(self):
        self.assertEqual(self.at(name="x", intent="about beta work", cwd="/home/u/code/alpha-run-worktree"), "beta")
        self.assertEqual(self.at(name="x", intent="nothing", cwd="/home/u/code/alpha-run-worktree"), "alpha")

    def test_tie_is_unattached(self):
        self.assertIsNone(self.at(name="shared-key work"))

    def test_no_match(self):
        self.assertIsNone(self.at(name="something else"))

    def test_handoff_item_line(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("Item:      alpha   Cell: x\nMachine: box\n")
        try:
            self.assertEqual(self.at(name="unrelated", intent=f.name + " please run"), "alpha")
        finally:
            os.unlink(f.name)


class HandoffItemLine(unittest.TestCase):
    """Real item ids have hyphens; round 2 found the hand-off pattern stopped at the first one."""
    items = [{"id": "agent-over-time", "match": []}, {"id": "clip-native", "match": []}, {"id": "stage-i-iii-vs-iv", "match": []}]
    ids = {i["id"] for i in items}

    def via_handoff(self, line):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(line + "\nMachine: box\n")
        try:
            return b.attach({"name": "x", "intent": f.name}, self.items, self.ids, Path("/nonexistent"))
        finally:
            os.unlink(f.name)

    def test_hyphenated_forms(self):
        self.assertEqual(self.via_handoff("Item:      agent-over-time   Cell: row · col"), "agent-over-time")
        self.assertEqual(self.via_handoff("Item: planning/dashboard/items/clip-native.json"), "clip-native")
        self.assertEqual(self.via_handoff("**Item:** stage-i-iii-vs-iv"), "stage-i-iii-vs-iv")


class PhilActions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, **kw):
        it = {"id": "q", "title": "T", "why": "W", "answer": "A", **kw}
        f = self.d / "q.json"
        f.write_text(json.dumps(it))
        return it, {"q": f}

    def acts(self, approve=None, accept=None):
        return {"approve": approve or {}, "accept_draft": accept or {}, "comments": {}, "needs": {}, "problems": {}}

    def test_approve_applies_only_to_wording_seen(self):
        it, files = self.item()
        b.apply_phil_actions([it], files, self.acts(approve={"q": {"at": "2026-11-19T09:00:00Z", "wording": {"title": "old", "why": "W", "answer": "A"}}}))
        self.assertNotIn("approved", it)
        b.apply_phil_actions([it], files, self.acts(approve={"q": {"at": "2026-11-19T09:00:00Z", "wording": {"title": "T", "why": "W", "answer": "A"}}}))
        self.assertEqual(it["approved"]["wording"], pages.wording_hash(it))
        self.assertIn("approved", json.loads(files["q"].read_text()))   # written to the item file

    def test_accept_refuses_a_draft_changed_after_phil_saw_it(self):
        # same day, later draft text: must not be applied (the round-1 review's reproduction)
        it, files = self.item(draft={"answer": "new text written at 15:00", "by": "s", "at": "2026-11-19"})
        b.apply_phil_actions([it], files, self.acts(accept={"q": {"at": "2026-11-19T09:00:00Z", "draft": {"answer": "text Phil saw at 09:00"}}}))
        self.assertEqual(it["answer"], "A")
        self.assertIn("draft", it)

    def test_accept_applies_the_draft_seen(self):
        it, files = self.item(draft={"answer": "B", "by": "s", "at": "2026-11-19"})
        b.apply_phil_actions([it], files, self.acts(accept={"q": {"at": "2026-11-19T09:00:00Z", "draft": {"answer": "B"}}}))
        self.assertEqual(it["answer"], "B")
        self.assertNotIn("draft", it)
        self.assertEqual(it["approved"]["wording"], pages.wording_hash(it))

    def test_edit_after_approval_is_detectable(self):
        it, files = self.item()
        it["approved"] = {"at": "2026-11-19", "wording": pages.wording_hash(it)}
        it["answer"] = "edited directly by a session"
        self.assertNotEqual(it["approved"]["wording"], pages.wording_hash(it))


class DailyCap(unittest.TestCase):
    def test_garbled_answer_counts_as_full_cap_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as t:
            dash = Path(t) / "dash"
            (dash / "items").mkdir(parents=True)
            for i in ("a", "b"):
                (dash / "items" / f"{i}.json").write_text(json.dumps({"id": i, "title": i}))
            fake = Path(t) / "bin"
            fake.mkdir()
            (fake / "claude").write_text("#!/bin/sh\necho not-json\n")
            (fake / "claude").chmod(0o755)
            env = {**os.environ, "PATH": f"{fake}:{os.environ['PATH']}"}
            r = subprocess.run([sys.executable, str(HERE / "daily_review.py"), "--dash", str(dash), "--cap", "5"],
                               capture_output=True, text=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            led = json.loads((dash / "review-spend.json").read_text())
            day = next(iter(led.values()))
            self.assertGreaterEqual(day["usd"], 5)
            r2 = subprocess.run([sys.executable, str(HERE / "daily_review.py"), "--dash", str(dash), "--cap", "5", "--force"],
                                capture_output=True, text=True, env=env)
            self.assertIn("cap reached", r2.stdout)


if __name__ == "__main__":
    unittest.main()
