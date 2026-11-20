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
        self.assertIn("Approve</b> = yes to every recommendation", page)
        self.assertIn("Settled so far (1)", page)
        self.assertEqual(sfr.relative_refs(page), [])  # send_for_review would accept it

    def test_final_spec_page(self):
        page = g.build({"title": "Grill: probe run", "questions": [], "spec": "# Spec\n<b>x</b>"})
        self.assertIn("the spec below is right", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertNotIn("Q1", page)

    def test_empty_round_refused(self):
        with self.assertRaises(SystemExit):
            g.build({"title": "x", "questions": []})


if __name__ == "__main__":
    unittest.main()
