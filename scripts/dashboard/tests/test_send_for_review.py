"""Tests for send_for_review.py and the builder's handling of review pages. Stdlib only:

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
import send_for_review as sfr  # noqa: E402
import build_dashboard as b  # noqa: E402

PAGE = "<!doctype html><html><head><title>Fig 3 redraw</title></head><body><img src='data:image/png;base64,AAAA'>{}</body></html>"


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = self.root / "chaudhari_lab/phil/planning"
        self.dash = self.plan / "dashboard"
        (self.dash / "items").mkdir(parents=True)
        (self.plan / "review_answers").mkdir()
        self.old = sfr.PLANNING
        sfr.PLANNING = self.plan
        self.src_dir = self.root / "chaudhari_lab/phil/plan-explainers/vista_bench"
        self.src_dir.mkdir(parents=True)

    def tearDown(self):
        sfr.PLANNING = self.old
        self.tmp.cleanup()

    def item(self, iid, **kw):
        (self.dash / "items" / f"{iid}.json").write_text(json.dumps({"id": iid, "title": iid.replace("-", " "), **kw}))

    def page(self, name="fig3.html", body="v1"):
        p = self.src_dir / name
        p.write_text(PAGE.format(body))
        return p

    def send(self, *args):
        return sfr.main(["send", *map(str, args)])

    def index(self):
        return json.loads((self.dash / "review-index.json").read_text())["entries"]

    def answer(self, state: dict, who="phil@example.edu"):
        (self.plan / "review_answers" / f"{who}.json").write_text(json.dumps(
            {"reviewer": who, "saved_at": "2026-11-20T00:00:00+00:00", "state": {"wd:review": json.dumps(state)}}))


class Send(Fixture):
    def test_frozen_copy_entry_and_index(self):
        self.item("paper-figures-update")
        src = self.page()
        self.assertEqual(self.send(src, "--item", "paper-figures-update", "--look", "Check panel c"), 0)
        es = self.index()
        self.assertEqual([e["id"] for e in es], ["fig3-v1"])
        e = es[0]
        self.assertEqual((e["title"], e["kind"], e["item"], e["item_how"], e["look"]),
                         ("Fig 3 redraw", "verdict", "paper-figures-update", "tag", "Check panel c"))
        src.write_text(PAGE.format("edited after sending"))   # the reviewed copy must not follow the original
        self.assertIn("v1", (self.dash / "review-fig3-v1.html").read_text())
        self.assertNotIn("edited", (self.dash / "review-fig3-v1.html").read_text())

    def test_second_send_is_v2_and_replaces_v1(self):
        src = self.page()
        self.send(src)
        self.page(body="v2 body")
        self.send(src, "--fyi")
        es = {e["id"]: e for e in self.index()}
        self.assertEqual(set(es), {"fig3-v1", "fig3-v2"})
        self.assertEqual(es["fig3-v1"]["replaced_by"], "fig3-v2")
        self.assertIsNone(es["fig3-v2"]["replaced_by"])
        self.assertEqual((es["fig3-v2"]["replaces"], es["fig3-v2"]["kind"]), ("fig3-v1", "fyi"))
        self.assertEqual(self.index()[0]["id"], "fig3-v2")   # newest first

    def test_refuses_relative_images_and_unknown_item(self):
        p = self.src_dir / "bad.html"
        p.write_text("<html><body><img src='panel_a.png'><a href='other.html'>link</a></body></html>")
        self.assertEqual(self.send(p), 2)
        self.assertFalse(list(self.dash.glob("review-*.html")))
        self.assertEqual(self.send(self.page(), "--item", "no-such-item"), 2)
        ok = self.src_dir / "ok.html"   # plain links and absolute URLs are fine
        ok.write_text("<html><body><a href='other.html'>x</a><img src='https://x.org/a.png'><script src='//cdn/x.js'></script></body></html>")
        self.assertEqual(self.send(ok), 0)

    def test_path_fallback_and_unattached(self):
        self.item("fusion-all-combos", sources=["plan-explainers/vista_bench/fusion-site/"])
        sub = self.src_dir / "fusion-site"
        sub.mkdir()
        (sub / "page.html").write_text(PAGE.format("x"))
        self.send(sub / "page.html", "--name", "fusion-page")
        self.send(self.page("loose.html"))
        es = {e["id"]: e for e in self.index()}
        self.assertEqual((es["fusion-page-v1"]["item"], es["fusion-page-v1"]["item_how"]), ("fusion-all-combos", "path"))
        self.assertEqual((es["loose-v1"]["item"], es["loose-v1"]["item_how"]), (None, "unattached"))

    def test_index_self_heals(self):
        self.send(self.page("a.html"))
        self.send(self.page("b.html"))
        (self.dash / "review-index.json").unlink()
        self.send(self.page("c.html"))   # the next send puts every entry back
        self.assertEqual({e["id"] for e in self.index()}, {"a-v1", "b-v1", "c-v1"})
        (self.dash / "review-index.json").write_text("{}")   # and so does a rebuild
        self.assertEqual(len(sfr.rebuild_index(self.dash)), 3)
        self.assertEqual(len(self.index()), 3)


class Verdicts(Fixture):
    def test_wait_returns_the_comment(self):
        self.send(self.page())
        self.assertEqual(sfr.main(["wait", "fig3-v1", "--hours", "0.0003", "--every", "0.2"]), 3)   # nothing yet: times out
        self.answer({"fig3-v1": {"seen": 1, "verdict": "changes", "comment": "label the y axis", "at": 2}})
        r = subprocess.run([sys.executable, str(HERE / "send_for_review.py"), "wait", "fig3-v1", "--hours", "0.01", "--every", "0.2"],
                           capture_output=True, text=True, env={**os.environ, "WD_PLANNING": str(self.plan)}, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("NEEDS CHANGES", r.stdout)
        self.assertIn("label the y axis", r.stdout)

    def test_builder_merges_verdicts(self):
        self.answer({"fig3-v1": {"seen": 5, "verdict": "approve", "at": 10}, "old-v1": {"seen": 3}})
        acts = b.load_phil_actions(self.plan)
        self.assertEqual(acts["review"]["fig3-v1"]["verdict"], "approve")
        self.assertEqual(acts["review"]["old-v1"], {"seen": 3})

    def test_builder_end_to_end(self):
        self.item("paper-figures-update")
        self.send(self.page(), "--item", "paper-figures-update", "--look", "panel c")
        (self.dash / "review-index.json").unlink()
        t = time.time() * 1000   # answered just now, so the builder must not archive it
        self.answer({"fig3-v1": {"seen": t, "verdict": "changes", "comment": "redo c", "at": t}})
        (self.plan / "hosts").mkdir(exist_ok=True)
        r = subprocess.run([sys.executable, str(HERE / "build_dashboard.py"), "--planning", str(self.plan),
                            "--hosts", str(self.plan / "hosts")], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([e["id"] for e in self.index()], ["fig3-v1"])   # rebuilt by the 5-minute rebuild
        acts = json.loads((self.dash / "phil-actions.json").read_text())
        rp = acts["review_pages"]["fig3-v1"]
        self.assertEqual((rp["verdict"], rp["comment"], rp["item"]), ("changes", "redo c", "paper-figures-update"))
        page = (self.dash / "index.html").read_text()
        data = json.loads(page.split("const D = ", 1)[1].split(";\nconst $ = ", 1)[0].replace("<\\/", "</"))
        self.assertEqual([e["id"] for e in data["reviews"]], ["fig3-v1"])
        it = next(i for i in data["items"] if i["id"] == "paper-figures-update")
        self.assertEqual([(r["id"], r["verdict"], r["comment"]) for r in it["reviews"]], [("fig3-v1", "changes", "redo c")])
        item_page = (self.dash / "paper-figures-update.html").read_text()   # the verdict shows on the item's own page
        self.assertIn("you asked for changes", item_page)
        self.assertIn("Your comment: redo c", item_page)


class Reviewers(Fixture):
    def test_newest_answer_wins_and_only_listed_reviewers_count(self):
        self.answer({"p-v1": {"verdict": "approve", "at": 100}}, who="phil@x.edu")
        self.answer({"p-v1": {"verdict": "changes", "comment": "colleague", "at": 200}}, who="amy@x.edu")
        self.assertEqual(sfr.verdicts(self.plan)["p-v1"]["reviewer"], "amy@x.edu")   # no list: everyone, newest wins
        self.assertEqual(b.load_phil_actions(self.plan)["review"]["p-v1"]["verdict"], "changes")
        (self.dash / "review-reviewers.json").write_text('["Phil@x.edu"]')
        v = sfr.verdicts(self.plan)["p-v1"]
        self.assertEqual((v["verdict"], v["reviewer"]), ("approve", "phil@x.edu"))
        self.assertEqual(b.load_phil_actions(self.plan)["review"]["p-v1"]["verdict"], "approve")
        self.assertEqual(sfr.entries(self.dash), [])   # the list file is not mistaken for an entry


class Versions(Fixture):
    def test_no_id_reuse_after_archive(self):
        src = self.page()
        self.send(src)
        old = (time.time() - 40 * 86400) * 1000
        self.assertEqual(sfr.archive(self.dash, {"fig3-v1": {"verdict": "approve", "at": old}}), ["fig3-v1"])
        self.answer({"fig3-v1": {"verdict": "approve", "at": old}})
        self.send(src)   # same name again: must not come back as fig3-v1 and inherit the old answer
        self.assertEqual([e["id"] for e in self.index()], ["fig3-v2"])
        self.assertNotIn("fig3-v2", sfr.verdicts(self.plan))

    def test_simultaneous_sends_get_different_numbers(self):
        src = self.page()
        procs = [subprocess.Popen([sys.executable, str(HERE / "send_for_review.py"), "send", str(src)],
                                  env={**os.environ, "WD_PLANNING": str(self.plan)}, stdout=subprocess.PIPE, text=True) for _ in range(4)]
        outs = [p.communicate(timeout=60)[0] for p in procs]
        ids = sorted(o.split()[1] for o in outs)
        self.assertEqual(ids, ["fig3-v1", "fig3-v2", "fig3-v3", "fig3-v4"])
        sfr.rebuild_index(self.dash)
        self.assertEqual(len(self.index()), 4)

    def test_mac_upload_includes_the_page_just_sent(self):
        uploads = {}

        def fake_run(cmd, **kw):   # stands in for gcloud storage cp; the mount never shows the upload
            uploads[cmd[-1]] = Path(cmd[-2]).read_text()
            return subprocess.CompletedProcess(cmd, 0, "", "")
        saved = (sfr.MAC, sfr.subprocess.run, os.environ.pop("WD_PLANNING", None))
        sfr.MAC, sfr.subprocess.run = True, fake_run
        try:
            self.assertEqual(self.send(self.page()), 0)
        finally:
            sfr.MAC, sfr.subprocess.run = saved[0], saved[1]
            if saved[2] is not None:
                os.environ["WD_PLANNING"] = saved[2]
        base = "gs://su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/"
        self.assertEqual(set(uploads), {base + "review-fig3-v1.html", base + "review-fig3-v1.json", base + "review-index.json"})
        self.assertEqual([e["id"] for e in json.loads(uploads[base + "review-index.json"])["entries"]], ["fig3-v1"])
        self.assertFalse(list(self.dash.glob("review-*")))   # nothing written through the Mac mount

    def test_failed_mac_upload_raises(self):
        saved = (sfr.MAC, sfr.subprocess.run, os.environ.pop("WD_PLANNING", None))
        sfr.MAC, sfr.subprocess.run = True, lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "denied")
        try:
            with self.assertRaises(SystemExit):
                self.send(self.page())
        finally:
            sfr.MAC, sfr.subprocess.run = saved[0], saved[1]
            if saved[2] is not None:
                os.environ["WD_PLANNING"] = saved[2]


class Archive(Fixture):
    def test_replaced_counts_from_when_it_was_replaced(self):
        src = self.page()
        self.send(src)
        e1 = self.dash / "review-fig3-v1.json"
        d = json.loads(e1.read_text())
        d["sent_at"] = "2026-01-01T00:00:00+00:00"   # sent long ago, unanswered
        e1.write_text(json.dumps(d))
        self.send(src)   # replaced just now
        self.assertEqual(sfr.archive(self.dash, {}), [])   # not archived the moment v2 arrives

    def test_fyi_done_once_opened(self):
        self.send(self.page(), "--fyi")
        self.send(self.page("v.html"))
        old = (time.time() - 40 * 86400) * 1000
        moved = sfr.archive(self.dash, {"fig3-v1": {"seen": old}, "v-v1": {"seen": old}})
        self.assertEqual(moved, ["fig3-v1"])   # an opened FYI is done; an opened verdict page is not

    def test_old_answered_and_replaced_pages_move(self):
        src = self.page()
        self.send(src)
        self.send(src)
        self.send(self.page("fresh.html"))
        es = {e["id"]: e for e in sfr.entries(self.dash)}
        later = time.time() + 40 * 86400
        old_ms = (time.time() - 1) * 1000
        moved = sfr.archive(self.dash, {"fig3-v2": {"verdict": "approve", "at": old_ms}}, now=later)
        self.assertEqual(set(moved), {"fig3-v1", "fig3-v2"})   # replaced 40 d ago; answered 40 d ago
        self.assertTrue((self.dash / "archive/review/review-fig3-v1.html").exists())
        self.assertEqual({e["id"] for e in sfr.entries(self.dash)}, {"fresh-v1"})   # unanswered stays, however old
        self.assertEqual(len(es), 3)


if __name__ == "__main__":
    unittest.main()
