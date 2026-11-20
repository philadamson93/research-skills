"""Tests for grill_page.py. Stdlib only:

    python3 -m unittest discover -s scripts/dashboard/tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import grill_page as g  # noqa: E402
import send_for_review as sfr  # noqa: E402


class GrillPage(unittest.TestCase):
    def test_round_page(self):
        page = g.build({"title": "Grill: probe run", "round": 2, "settled": ["cohort -> NSCLC"],
                        "questions": [{"title": "Sample size", "body": "Two options:\n\n- 200\n- 500",
                                       "recommend": "200 <script>alert(1)</script>"},
                                      {"title": "Split", "body": "Use `val`?", "recommend": "yes"}]})
        self.assertIn("Q1 · Sample size", page)
        self.assertIn("Q2 · Split", page)
        self.assertIn("<li>500</li>", page)
        self.assertIn("<code>val</code>", page)
        self.assertNotIn("<script>alert", page)
        self.assertIn("Round 2 · 2 questions", page)
        self.assertIn("<b>Approve</b> with nothing changed = yes to every recommendation", page)
        # free-form questions: "Recommended" starts selected, Other's box starts filled with the recommendation
        self.assertIn("name='q2' value='yes' checked> Recommended", page)
        self.assertIn("<textarea id='t2' placeholder='your answer'>yes</textarea>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;</textarea>", page)
        self.assertIn("\\u003cscript>", page)  # the data block can't close its own <script> tag
        self.assertIn("Settled so far (1)", page)
        self.assertEqual(sfr.relative_refs(page), [])  # send_for_review would accept it

    def test_options_and_multi(self):
        page = g.build({"title": "Grill: x", "questions": [
            {"title": "N", "recommend": "200", "options": ["200", {"label": "500", "detail": "a day more GPU"}]},
            {"title": "Sites", "multi": True, "recommend": ["lung", "liver"], "options": ["lung", "liver", "bone"]}]})
        self.assertIn("name='q1' value=\"200\" checked> 200<span class=tag>recommended</span>", page)
        self.assertIn("name='q1' value=\"500\"> 500<span class=d>— a day more GPU</span>", page)
        self.assertIn("<textarea id='t1' placeholder='your answer'>200</textarea>", page)
        self.assertIn("type='checkbox' name='q2' value=\"liver\" checked>", page)
        self.assertIn("type='checkbox' name='q2' value=\"bone\">", page)
        self.assertIn("Other (add your own)", page)
        self.assertIn('{"multi": true, "rec": ["lung", "liver"], "title": "Sites"}', page)

    def test_recommendation_must_be_an_option(self):
        with self.assertRaises(SystemExit):
            g.build({"title": "x", "questions": [{"title": "N", "recommend": "300", "options": ["200", "500"]}]})
        with self.assertRaises(SystemExit):
            g.build({"title": "x", "questions": [{"title": "S", "multi": True, "recommend": ["kidney"], "options": ["lung"]}]})

    def test_final_spec_page(self):
        page = g.build({"title": "Grill: probe run", "questions": [], "spec": "# Spec\n<b>x</b>"})
        self.assertIn("the spec below is right", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertNotIn("Q1", page)
        self.assertNotIn("<script>", page)

    def test_empty_round_refused(self):
        with self.assertRaises(SystemExit):
            g.build({"title": "x", "questions": []})


if __name__ == "__main__":
    unittest.main()
