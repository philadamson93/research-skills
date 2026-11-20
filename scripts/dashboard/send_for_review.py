#!/usr/bin/env python3
"""Send an HTML page to the work dashboard's "To review" tab. Stdlib only.

    python3 send_for_review.py send PAGE --item ITEM_ID --look "what to look at" [--fyi] [--name NAME] [--by SESSION]
    python3 send_for_review.py wait ENTRY_ID [--hours 24]      # run in the background; exits when Phil answers
                                                                # or when a newer version is sent (exit 4)
    python3 send_for_review.py index                            # rebuild review-index.json from the entry files

`send` freezes a copy of PAGE into planning/dashboard/ as review-<name>-v<N>.html (the review server serves that
folder flat, so no server change), writes its entry review-<name>-v<N>.json next to it, rewrites
review-index.json (the list the dashboard checks every 10 s), and prints the website link. Sending the same
name again makes the next version and marks the earlier one replaced.

The index is rebuilt from the entry files every time, here and by build_dashboard.py, so a send that loses a
race with another machine's send is put back by the next send or the 5-minute rebuild.

Phil's answers ride on the dashboard's existing click store: localStorage key "wd:review" =
{entry_id: {"seen": ms, "verdict": "approve"|"changes", "comment": str, "at": ms}}, saved by the review server
to planning/review_answers/<email>.json about a second after each click.
"""
from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MAC = sys.platform == "darwin"
PLANNING = Path(os.environ.get("WD_PLANNING") or ("/Volumes/su-vista-uscentral1/chaudhari_lab/phil/planning" if MAC
                                                  else "/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning"))
BUCKET = "gs://su-vista-uscentral1"
SITE = "https://vista-explorer-web-trxt7vzeba-uc.a.run.app/phil-dashboard/"
PREFIX = "review-"
INDEX = "review-index.json"
ENTRY_RE = re.compile(r"^review-(?P<name>[a-z0-9][a-z0-9-]*)-v(?P<v>\d+)\.json$")
ARCHIVE_DAYS = 30


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60].strip("-") or "page"


def page_title(text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    return html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""


def relative_refs(text: str) -> list[str]:
    """Files the page loads by relative path. A frozen copy in another folder would show them broken."""
    loaded = re.findall(r"""<(?:img|script|link|iframe|source|video|audio)\b[^>]*?(?:src|href)\s*=\s*["']([^"'#?]+)["']""", text, re.I)
    bad = [r for r in loaded if not re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|/)", r, re.I)]
    return sorted(set(bad))


def write_atomic(path: Path, data: bytes | str) -> None:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if MAC and "WD_PLANNING" not in os.environ:
        # The Mac's mount can accept a write and never send it to the bucket (270 files lost, 2026-09), so upload
        # with gcloud instead; raise on failure rather than report a send that never landed.
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=path.suffix) as f:
            f.write(raw)
        dest = BUCKET + "/chaudhari_lab/" + str(path).split("/chaudhari_lab/", 1)[1]
        r = subprocess.run(["gcloud", "storage", "cp", f.name, dest], capture_output=True, text=True)
        os.unlink(f.name)
        if r.returncode:
            raise SystemExit(f"ERROR: upload to {dest} failed: {r.stderr.strip()[-300:]}")
        return
    tmp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def entries(dash: Path) -> list[dict]:
    out = []
    for f in sorted(dash.glob(PREFIX + "*.json")):
        if f.name == INDEX or not ENTRY_RE.match(f.name):
            continue
        try:
            e = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(e, dict) and e.get("id") and (dash / e.get("file", "")).is_file():
            out.append(e)
    return out


def used_versions(dash: Path, name: str) -> set[int]:
    """Every version number ever used for this name, archived ones included, so an id (and the answer saved
    under it) is never reused."""
    vs = set()
    for d in (dash, dash / "archive" / "review"):
        for f in d.glob(f"{PREFIX}{name}-v*.json") if d.exists() else []:
            m = ENTRY_RE.match(f.name)
            if m and m.group("name") == name:
                vs.add(int(m.group("v")))
    return vs


def rebuild_index(dash: Path, just_sent: dict | None = None) -> list[dict]:
    """review-index.json from the entry files: newest first, each marked with the version that replaced it.
    just_sent is added even if the folder listing doesn't show it yet (the Mac mount lags its own uploads)."""
    es = entries(dash)
    if just_sent and just_sent["id"] not in {e["id"] for e in es}:
        es.append(dict(just_sent))
    newest = {}
    for e in es:
        if e["version"] > newest.get(e["name"], {"version": 0})["version"]:
            newest[e["name"]] = e
    for e in es:
        top = newest[e["name"]]
        e["replaced_by"] = top["id"] if top["id"] != e["id"] else None
    es.sort(key=lambda e: (e.get("sent_at", ""), e["version"]), reverse=True)   # same-second sends: newer version first
    write_atomic(dash / INDEX, json.dumps({"written_at": now_iso(), "entries": es}, indent=1, ensure_ascii=False))
    return es


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def match_item(source: Path, name: str, items_dir: Path) -> str | None:
    """Path fallback for an untagged page: the item whose sources, readbacks or watched paths contain the page
    (or its folder), else the item whose id is the page name. None if nothing or more than one matches."""
    src = str(source)
    rel = src.split("/chaudhari_lab/phil/", 1)[-1]   # plan-explainers/... or planning/...
    hits = set()
    for f in sorted(items_dir.glob("*.json")) if items_dir.exists() else []:
        try:
            it = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        paths = list(it.get("sources") or []) + [p for r in it.get("runs") or [] for p in [r.get("readback")] + list(r.get("watch") or []) if p]
        for p in paths:
            p = str(p).rstrip("/")
            pr = p.split("/chaudhari_lab/phil/", 1)[-1]
            if pr and (rel == pr or rel.startswith(pr + "/")):
                hits.add(it.get("id"))
        if it.get("id") == name:
            hits.add(it["id"])
    hits.discard(None)
    return hits.pop() if len(hits) == 1 else None


def send(a) -> int:
    dash = PLANNING / "dashboard"
    src = Path(a.page).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() not in (".html", ".htm"):
        print(f"ERROR: {src} is not an HTML file", file=sys.stderr)
        return 2
    text = src.read_text(encoding="utf-8", errors="replace")
    refs = relative_refs(text)
    if refs:   # raise, never send a page that will show broken images: the fix is to inline them
        print(f"ERROR: {src.name} loads {len(refs)} file(s) by relative path ({', '.join(refs[:5])}), which a copy "
              "can't see. Inline them (images as data: URIs, scripts and styles in the page) and send again.", file=sys.stderr)
        return 2
    name = slug(a.name or src.stem)
    items_dir = dash / "items"
    item = a.item
    if item and not (items_dir / f"{item}.json").is_file():
        print(f"ERROR: no dashboard item {item} (looked for {items_dir}/{item}.json)", file=sys.stderr)
        return 2
    how = "tag" if item else None
    if not item:
        item = match_item(src, name, items_dir)
        how = "path" if item else "unattached"
    prev = [e for e in entries(dash) if e["name"] == name]
    v = max(used_versions(dash, name), default=0) + 1
    if not MAC:   # claim the number with an exclusive create, so two sends of one name at once can't share it
        while True:
            try:
                os.close(os.open(dash / f"{PREFIX}{name}-v{v}.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                v += 1
    eid = f"{name}-v{v}"
    fname = f"{PREFIX}{eid}.html"
    write_atomic(dash / fname, text)   # the frozen copy: later edits to the original don't change what was reviewed
    entry = {
        "id": eid, "name": name, "version": v, "file": fname,
        "title": a.title or page_title(text) or src.stem, "look": a.look or "", "kind": "fyi" if a.fyi else "verdict",
        "item": item, "item_how": how, "source": str(src), "bytes": len(text.encode("utf-8")),
        "sent_at": now_iso(), "by": a.by or os.environ.get("CLAUDE_SESSION_NAME", ""), "host": socket.gethostname(),
        "user": getpass.getuser(), "replaces": prev and max(prev, key=lambda e: e["version"])["id"] or None,
    }
    write_atomic(dash / f"{PREFIX}{eid}.json", json.dumps(entry, indent=1, ensure_ascii=False))
    rebuild_index(dash, entry)
    print(f"sent {eid}  item={item or 'unattached'} ({how})  kind={entry['kind']}")
    print(f"link: {SITE}#r={eid}")
    if entry["kind"] == "verdict":
        print(f"wait: python3 {Path(__file__).resolve()} wait {eid}   (run in the background, only if you are "
              "ending your turn; skip it while iterating with Phil in chat)")
        if entry["replaces"]:
            print(f"      any wait still running on {entry['replaces']} ends by itself within 30 s")
    return 0


def reviewers(plan: Path = PLANNING) -> set[str] | None:
    """Whose answers count: planning/dashboard/review-reviewers.json, a JSON list of sign-in emails. Anyone can
    open the dashboard, so without this a colleague's click would wake a session. None (file absent) = everyone."""
    f = plan / "dashboard" / "review-reviewers.json"
    try:
        return {str(x).lower() for x in json.loads(f.read_text())}
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def verdicts(plan: Path = PLANNING) -> dict:
    """Answers to review pages from the people who count: {entry_id: {..., "reviewer": email}}, newest answer wins."""
    out = {}
    allowed = reviewers(plan)
    for f in sorted((plan / "review_answers").glob("*.json")):
        try:
            doc = json.loads(f.read_text())
            val = json.loads((doc.get("state") or {}).get("wd:review") or "{}")
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        who = doc.get("reviewer") or f.stem
        if allowed is not None and who.lower() not in allowed:
            continue
        for eid, v in (val or {}).items():
            if not isinstance(v, dict):
                continue
            if eid not in out or (v.get("at") or v.get("seen") or 0) > (out[eid].get("at") or out[eid].get("seen") or 0):
                out[eid] = {**v, "reviewer": who}
    return out


def newer_version(dash: Path, eid: str) -> str | None:
    """The id of a later version of this entry's page, if one was sent (archived ones count), else None."""
    m = re.match(r"^(?P<name>.+)-v(?P<v>\d+)$", eid)
    if not m:
        return None
    later = [v for v in used_versions(dash, m.group("name")) if v > int(m.group("v"))]
    return f"{m.group('name')}-v{max(later)}" if later else None


def wait(a) -> int:
    """Exit 0 with the verdict when one appears for the entry, 3 after the time limit, 4 as soon as a newer version
    of the page is sent. Meant for a background run, so a finished session wakes up when Phil answers.

    Exit 4 is what keeps waits from piling up: each re-send used to leave the previous version's 24-hour wait
    sleeping on a page nobody will answer (eleven at once, 2026-11-20). Now the old wait ends by itself within
    one check, whichever session or machine sent the new version."""
    deadline = time.time() + a.hours * 3600
    dash = PLANNING / "dashboard"
    while time.time() < deadline:
        v = verdicts().get(a.entry, {})
        if not v.get("verdict"):
            newer = newer_version(dash, a.entry)
            if newer:
                print(f"REPLACED: {a.entry} by {newer}; this wait ended. Nothing to do here.")
                return 4
        if v.get("verdict"):
            word = "APPROVED" if v["verdict"] == "approve" else "NEEDS CHANGES"
            print(f"{word}: {a.entry} by {v.get('reviewer', '?')} at "
                  f"{datetime.fromtimestamp((v.get('at') or 0) / 1000, timezone.utc).isoformat(timespec='seconds')}")
            if v.get("comment"):
                print("comment: " + v["comment"])
            return 0
        time.sleep(a.every)
    print(f"no verdict on {a.entry} after {a.hours} h; it waits on the dashboard item")
    return 3


def archive(dash: Path, answers: dict, now: float | None = None) -> list[str]:
    """Move review pages answered (or, for FYI, opened) more than 30 days ago, and versions replaced more than
    30 days ago, into dashboard/archive/review/. Returns the entry ids moved."""
    now = now or time.time()
    es = {e["id"]: e for e in entries(dash)}
    cut = now - ARCHIVE_DAYS * 86400
    moved = []
    for e in es.values():
        ans = answers.get(e["id"], {})
        done_ms = ans.get("at") if e.get("kind") == "verdict" else ans.get("seen")
        later = [x for x in es.values() if x["name"] == e["name"] and x["version"] > e["version"] and x.get("sent_at")]
        replaced_at = min(datetime.fromisoformat(x["sent_at"]).timestamp() for x in later) if later else None
        if (done_ms and done_ms / 1000 < cut) or (replaced_at and replaced_at < cut):
            dest = dash / "archive" / "review"
            dest.mkdir(parents=True, exist_ok=True)
            for f in (e["file"], f"{PREFIX}{e['id']}.json"):
                if (dash / f).exists():
                    os.replace(dash / f, dest / f)
            moved.append(e["id"])
    return moved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send", help="send a page for review")
    s.add_argument("page")
    s.add_argument("--item", help="dashboard item id (planning/dashboard/items/<id>.json); omit to match by path")
    s.add_argument("--look", help="one sentence: what Phil should look at or decide")
    s.add_argument("--fyi", action="store_true", help="for information only: opening it is enough, no verdict")
    s.add_argument("--name", help="stable name across versions (default: the file name)")
    s.add_argument("--title", help="title on the list (default: the page's <title>)")
    s.add_argument("--by", help="sending session's name")
    w = sub.add_parser("wait", help="block until the entry has a verdict")
    w.add_argument("entry")
    w.add_argument("--hours", type=float, default=24)
    w.add_argument("--every", type=float, default=30, help="seconds between checks")
    sub.add_parser("index", help="rebuild review-index.json")
    a = ap.parse_args(argv)
    if a.cmd == "send":
        return send(a)
    if a.cmd == "wait":
        return wait(a)
    print(f"{len(rebuild_index(PLANNING / 'dashboard'))} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
