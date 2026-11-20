#!/usr/bin/env python3
"""Turn one /grill round into a self-contained HTML page for the dashboard's "To review" tab. Stdlib only.

    python3 grill_page.py ROUND.json OUT.html

ROUND.json:
    {"title": "Grill: <the work>", "round": 2,
     "context": "one or two plain sentences on what is being decided",
     "settled": ["<question> -> <answer>", ...],                    # decided in earlier rounds
     "questions": [{"title": "...", "body": "...", "recommend": "..."}, ...],
     "spec": "<markdown of the one-page spec>"}                      # final round only; questions may be []

Body and spec text are escaped; blank lines make paragraphs, lines starting "- " make bullets, `x` and **x**
work inline. The page tells Phil how to answer: Approve = yes to every recommendation (or, on the final round,
the spec is approved); Needs changes + a comment answers per question ("Q2: no, use 200 patients").
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

CSS = """body{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#1d1d1f}
h1{font-size:22px;margin:0 0 4px}.sub{color:#666;margin-bottom:16px}
.how{background:#f2f6ff;border:1px solid #c9d8ff;border-radius:8px;padding:10px 14px;margin:12px 0 20px}
.q{border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:14px 0}
.q h2{font-size:17px;margin:0 0 6px}.rec{background:#f3fbf3;border-left:4px solid #3a9a3a;padding:6px 10px;margin-top:8px}
details{margin:10px 0 18px}pre{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:12px}
code{background:#f2f2f2;padding:0 3px;border-radius:3px}ul{margin:4px 0 4px 20px;padding:0}"""


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def block(text: str) -> str:
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l for l in para.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l.lstrip()[2:])}</li>" for l in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(inline(l) for l in lines) + "</p>")
    return "".join(out)


def build(r: dict) -> str:
    qs, spec = r.get("questions") or [], r.get("spec") or ""
    if not qs and not spec:
        raise SystemExit("ERROR: the round has no questions and no spec")
    title = r.get("title") or "Grill"
    rnd = r.get("round")
    sub = (f"Round {int(rnd)} · " if rnd else "") + (f"{len(qs)} question{'s' * (len(qs) != 1)}" if qs else "final check")
    if qs:
        how = ("<b>How to answer.</b> <b>Approve</b> = yes to every recommendation below. Otherwise press "
               "<b>Needs changes</b> and write one line per question you want different, e.g. "
               "<i>Q2: no, use 200 patients</i>. Questions you don't mention take the recommendation.")
    else:
        how = ("<b>How to answer.</b> <b>Approve</b> = the spec below is right and the build can start. "
               "<b>Needs changes</b> = say what is wrong in the comment and you get a revised page.")
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>",
             f"<style>{CSS}</style></head><body><h1>{html.escape(title)}</h1><div class='sub'>{html.escape(sub)}</div>"]
    if r.get("context"):
        parts.append(block(r["context"]))
    parts.append(f"<div class='how'>{how}</div>")
    if r.get("settled"):
        parts.append(f"<details><summary>Settled so far ({len(r['settled'])})</summary><ul>"
                     + "".join(f"<li>{inline(s)}</li>" for s in r["settled"]) + "</ul></details>")
    for i, q in enumerate(qs, 1):
        parts.append(f"<div class='q'><h2>Q{i} · {inline(q.get('title', ''))}</h2>{block(q.get('body', ''))}"
                     f"<div class='rec'><b>Recommended:</b> {inline(q.get('recommend', ''))}</div></div>")
    if spec:
        parts.append(f"<h2>The spec</h2><pre>{html.escape(spec)}</pre>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    page = build(json.loads(Path(argv[0]).read_text()))
    Path(argv[1]).write_text(page)
    print(argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
