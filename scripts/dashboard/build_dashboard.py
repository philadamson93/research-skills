#!/usr/bin/env python3
"""Build the work dashboard: one self-contained HTML page on the mount.

Joins three things nobody has to maintain by hand:
  - host snapshots   planning/dashboard/hosts/<host>.json   (snapshot_sessions.py)
  - repo boards      planning/boards/<repo>.md
  - program briefs   planning/programs/<slug>.md

    python3 build_dashboard.py [--planning <dir>] [--hosts <dir>] [--out <file>]

Reads only; writes the one HTML file (atomically).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import time

import pages
from datetime import datetime, timezone
from pathlib import Path

PLANNING = "/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning"
GLYPHS = "▶⏸✅⛔○◐⚠●✎"
RECENT_H = 72          # idle sessions newer than this are "just finished"
STALE_BOARD_DAYS = 14  # board items older than this are flagged
HOST_STALE_MIN = 20    # a host snapshot older than this is flagged


def epoch(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def words(s: str) -> set[str]:
    stop = {"with", "from", "that", "this", "stage", "program", "vista", "into", "over", "kickoff",
            "handoff", "review", "status", "check", "results", "session", "html", "runs", "test"}
    return {w for w in re.findall(r"[a-z0-9]{4,}", (s or "").lower()) if w not in stop}


# ---------- briefs ----------

def word_glyph(text: str) -> str:
    t = text.lower()
    for pat, g in ((r"\blanded\b|✓|\bdone\b|completed", "✅"), (r"\bdraft\b", "✎"),
                   (r"\bfuture\b|\bplanned\b", "○"), (r"\bbuilt\b|pushed", "◐"),
                   (r"blocked", "⛔"), (r"running|in flight", "▶")):
        if re.search(pat, t):
            return g
    return "?"

def parse_brief(path: Path) -> dict | None:
    text = path.read_text(errors="replace")
    m = re.search(r"(?m)^# (.+)$", text)
    if not m:
        return None
    upd = re.search(r"\*\*Last updated\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    stages = []
    in_stages = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_stages = line.strip().lower() == "## stages"
            continue
        if in_stages and re.match(r"^\|\s*[0-9]", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            status = cells[3]
            g = next((ch for ch in status if ch in GLYPHS), None)
            if g is None:  # glyph in another column, or status written as words
                g = next((ch for c in cells[1:] for ch in c if ch in GLYPHS), None) or word_glyph(" ".join(cells[1:]))
                status = next((c for c in cells[1:] if any(ch in c for ch in GLYPHS)), " ".join(cells[1:4]))
            plan = cells[4] if len(cells) > 4 else ""
            stages.append({
                "n": cells[0], "name": re.sub(r"\*\*|`", "", cells[1])[:160],
                "glyph": g, "status": re.sub(r"\*\*|`", "", status)[:260],
                "has_plan": bool(plan) and "no plan" not in plan.lower(),
            })
    done_when = []
    dm = re.search(r"(?ms)^## Done when\s*\n(.*?)(?=^## )", text)
    if dm:
        done_when = [re.sub(r"^\s*-\s*", "", l).strip() for l in dm.group(1).splitlines() if l.strip().startswith("-")][:5]
    decided = re.findall(r"(?m)^- \*\*(\d{4}-\d{2}-\d{2})", text)
    open_decided = [s for s in stages if s["glyph"] in "▶◐⚠" or (s["glyph"] == "○" and s["has_plan"])]
    unplanned = [s for s in stages if s["glyph"] == "○" and not s["has_plan"]]
    drafts = [s for s in stages if s["glyph"] == "✎"]
    if open_decided:
        road = "decided work left"
    elif any(s["glyph"] in "⏸⛔" for s in stages):
        road = "waiting or blocked"
    elif stages:
        road = "end of decided work"
    else:
        road = "no stage table"
    return {
        "slug": path.stem, "title": m.group(1).strip()[:160],
        "updated": upd.group(1) if upd else None,
        "stages": stages, "done_when": done_when,
        "last_decision": max(decided) if decided else None,
        "road": road, "unplanned": [s["name"] for s in unplanned],
        "drafts": [s["n"] + ". " + s["name"] for s in drafts],
    }


# ---------- boards ----------

ITEM_HDR = re.compile(r"^(?P<name>.+?) · program (?P<prog>[\w\-]+)(?P<rest>.*)$")


def parse_board(path: Path) -> list[dict]:
    items = []
    lines = path.read_text(errors="replace").splitlines()
    for i, line in enumerate(lines):
        m = ITEM_HDR.match(line.strip())
        if not m or line.startswith(("<", " ")):
            continue
        rest = m.group("rest")
        g = next((ch for ch in rest if ch in GLYPHS), "?")
        dm = re.findall(r"·\s*(\d{2}-\d{2})\s*$", line.strip())
        nxt = ""
        if i + 1 < len(lines) and lines[i + 1].lower().startswith("next:"):
            nxt = lines[i + 1][5:].strip()
        items.append({
            "repo": path.stem, "name": re.sub(r"\*\*|`", "", m.group("name"))[:160],
            "program": m.group("prog"), "glyph": g,
            "state": re.sub(r"\*\*|`", "", rest.strip(" ·"))[:200],
            "date": dm[-1] if dm else None,
            "next": re.sub(r"\*\*", "", nxt)[:400],
        })
    return items


def board_age_days(mmdd: str | None, now: datetime) -> int | None:
    if not mmdd:
        return None
    try:
        d = datetime(now.year, int(mmdd[:2]), int(mmdd[3:]), tzinfo=timezone.utc)
        if d > now:
            d = d.replace(year=now.year - 1)
        return (now - d).days
    except ValueError:
        return None


# ---------- sessions ----------

def link_program(s: dict, briefs: dict[str, dict], board_items: list[dict]) -> str | None:
    p = s.get("parsed", {})
    # Strongest signal after a declared program: the session's worktree folder or branch
    # named in a board item's text.
    keys = []
    if s.get("cwd") and Path(s["cwd"]).name not in ("code", "philadamson"):
        keys.append(Path(s["cwd"]).name)
    if s.get("branch") and s["branch"] not in ("HEAD", "main", "master"):
        keys.append(s["branch"])
    keys += [k for k in re.findall(r"\b(?:feat|fix)/[\w.\-]+", s.get("last_text_tail", ""))][:3]
    declared = " ".join(filter(None, [p.get("resume_program"), p.get("close_program"), p.get("resume_brief")]))
    norm = lambda x: re.sub(r"[^a-z0-9.]+", " ", x.lower()).strip()
    dn = " " + norm(declared) + " "
    for slug in sorted(briefs, key=len, reverse=True):
        if " " + norm(slug) + " " in dn or " " + norm(briefs[slug]["title"]) + " " in dn:
            return slug
    for k in keys:
        for it in board_items:
            if it.get("program_resolved") and k in (it["name"] + " " + it["next"]):
                return it["program_resolved"]
    # Repo board: if every live item on the session's repo board is one program, use it.
    if s.get("cwd"):
        folder = Path(s["cwd"]).name
        progs = {it["program_resolved"] for it in board_items
                 if it.get("program_resolved") and folder.startswith(it["repo"])}
        if len(progs) == 1:
            return progs.pop()
    hay = words(" ".join(filter(None, [s.get("name"), s.get("intent", "")[:300], declared])))
    best, score = None, 0
    for slug, b in briefs.items():
        w = words(slug.replace("-", " ") + " " + b["title"])
        sc = len(hay & w)
        if sc > score:
            best, score = slug, sc
    return best if score >= 2 else None


def bucket(s: dict, now: float) -> str:
    live = s.get("live")
    p = s.get("parsed", {})
    upd = epoch(s.get("updated_at")) or 0
    if live == "waiting" or s.get("tempo") == "blocked" or s.get("needs"):
        return "waiting"
    if live in ("busy", "shell"):
        return "working"
    if s.get("job_state") == "failed" or p.get("failed"):
        return "failed"
    yours = (p.get("close_yours") or "").strip().lower()
    asks = bool(p.get("needs_input")) or (yours and yours not in ("none", "none.", "-"))
    recent = now - upd < RECENT_H * 3600
    if recent and asks:
        return "asked"
    if recent:
        return "finished"
    return "parked"


STATUS_RE = re.compile(r"^\s*\**\s*Status\s*\**\s*:\s*\**\s*(running|waiting on phil|done|failed)\b\**\s*[—–:-]*\s*(.*)$", re.I)


def resolve(p: str, plan: Path) -> Path:
    return Path(p) if p.startswith("/") else plan.parent / p   # planning-relative paths start "planning/"


def readback_status(path: Path) -> tuple[str | None, str]:
    """The one status line at the top of a readback (first 15 lines). None if absent."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for _, line in zip(range(15), fh):
                m = STATUS_RE.match(line)
                if m:
                    return m.group(1).lower(), m.group(2).strip()[:300]
    except OSError:
        pass
    return None, ""


def run_status(run: dict, plan: Path, now: float, hosts_by_name: dict) -> dict:
    """Judge a run by its readback's status line; 'possibly died' only if quiet AND its job is gone."""
    rb = run.get("readback")
    newest = 0.0
    paths = ([rb] if rb else []) + run.get("watch", [])
    for w in paths:
        pth = resolve(w, plan)
        try:
            newest = max(newest, pth.stat().st_mtime)
        except OSError:
            pass
    age_h = (now - newest) / 3600 if newest else None
    st, summary = (None, "")
    if rb and resolve(rb, plan).exists():
        st, summary = readback_status(resolve(rb, plan))
    if rb and not (rb.startswith("/mnt/") or rb.startswith("planning/")):
        state = "readback not on the mount"   # a repo docs/session path can't be read from other machines
    elif not rb or not resolve(rb, plan).exists():
        state = "no readback yet"
    elif st is None:
        state = "status unknown"
    elif st == "running":
        state = "running"
        if age_h is not None and age_h > run.get("quiet_h", 6):
            h = hosts_by_name.get(run.get("machine", ""))
            job = (run.get("job") or "").strip()
            if not h or h["stale"] or not job:   # no report, or nothing named to look for: can't tell
                state = "quiet, can't check the job"
            else:
                mach = h.get("machine") or {}
                cmds = mach.get("procs") or [j["cmd"] for j in mach.get("jobs", [])]
                state = "running, job alive" if any(job in c for c in cmds) else "possibly died"
    else:
        state = {"waiting on phil": "waiting on Phil", "done": "done", "failed": "failed"}[st]
    return {**run, "state": state, "summary": summary,
            "newest": datetime.fromtimestamp(newest, timezone.utc).isoformat() if newest else None,
            "age_h": round(age_h, 1) if age_h is not None else None}


ITEM_LINE = re.compile(r"(?im)^\s*\**\s*Item\s*\**\s*:\s*\**\s*(?:\S*?items/)?([a-z0-9][\w.-]*?)(?:\.json)?(?=\s|$)")


def attach(s: dict, items: list, ids: set, plan: Path) -> str | None:
    """The item a session belongs to: the one it names, else a single best name match, else none."""
    named = (s.get("parsed") or {}).get("item")
    if named in ids:
        return named
    intent = (s.get("intent") or "").strip()
    first = intent.split()[0] if intent else ""
    if first.endswith(".md"):            # sessions started on a hand-off file: read its Item: line
        try:
            with open(resolve(first, plan) if not first.startswith("/") else first, encoding="utf-8", errors="replace") as fh:
                for _, line in zip(range(15), fh):
                    m = ITEM_LINE.match(line)
                    if m and m.group(1) in ids:
                        return m.group(1)
        except OSError:
            pass
    best = {}
    # What the session says it is about beats where it happens to run: folder and branch only as a fallback.
    for keys in (("name", "intent"), ("cwd", "branch")):
        hay = " ".join(str(s.get(k) or "") for k in keys).lower()
        for it in items:
            hits = [m.lower() for m in it.get("match", []) if m and m.lower() in hay]
            if hits:
                best[it["id"]] = max(len(h) for h in hits)
        if best:
            break
    if not best:
        return None
    top = max(best.values())
    winners = [i for i, v in best.items() if v == top]
    return winners[0] if len(winners) == 1 else None   # a tie means we can't tell: leave it unattached


def load_phil_actions(plan: Path) -> dict:
    """Phil's clicks and comments, as saved by the review server (planning/review_answers/<email>.json)."""
    merged = {"approve": {}, "accept_draft": {}, "comments": {}, "needs": {}, "problems": {}, "saved_at": None}
    for f in sorted((plan / "review_answers").glob("*.json")):
        try:
            doc = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        merged["saved_at"] = max(filter(None, [merged["saved_at"], doc.get("saved_at")]), default=None)
        for k, v in (doc.get("state") or {}).items():
            if not k.startswith("wd:"):
                continue
            try:
                val = json.loads(v)
            except (TypeError, json.JSONDecodeError):
                continue
            if k == "wd:approve":
                merged["approve"].update(val)
            elif k == "wd:accept-draft":
                merged["accept_draft"].update(val)
            elif k == "wd:needs":
                merged["needs"].update(val)
            elif k == "wd:probs":
                merged["problems"].update(val)
            elif k.startswith("wd:c:"):
                merged["comments"].setdefault(k[5:], {}).update(val)
    return merged


def apply_phil_actions(items: list, files: dict, acts: dict) -> list[str]:
    """Write Phil's Approve / Accept clicks into item files. Returns what changed."""
    changed = []
    for it in items:
        iid = it["id"]
        acc = acts["accept_draft"].get(iid)
        if acc and it.get("draft") and acc.get("draft") == pages.draft_seen(it):   # only the draft Phil actually saw
            for k in ("title", "why", "answer"):
                if k in it["draft"]:
                    it[k] = it["draft"][k]
            it.pop("draft")
            it["approved"] = {"at": acc["at"][:10], "wording": pages.wording_hash(it)}
            changed.append(f"{iid}: accepted draft")
        ap = acts["approve"].get(iid)
        wording = {k: it.get(k) for k in ("title", "why", "answer")}
        apr0 = it.get("approved") or {}
        stale = bool(apr0.get("wording")) and apr0["wording"] != pages.wording_hash(it)
        newer = not apr0 or (stale and ap and ap["at"][:10] >= apr0.get("at", ""))
        if ap and newer and ap.get("wording") == wording:   # only the wording Phil actually saw
            it["approved"] = {"at": ap["at"][:10], "wording": pages.wording_hash(it)}
            changed.append(f"{iid}: wording approved")
        apr = it.get("approved")
        if apr and not apr.get("wording"):          # approved before fingerprints existed: trust it, record it
            apr["wording"] = pages.wording_hash(it)
            changed.append(f"{iid}: wording fingerprint recorded")
    for it in items:
        if any(c.startswith(it["id"] + ":") for c in changed):
            clean = {k: v for k, v in it.items() if k not in DERIVED}
            pages.write_atomic(files[it["id"]], json.dumps(clean, indent=1, ensure_ascii=False))
    return changed


DERIVED = {"file_updated", "sessions", "runs_status", "page", "needs_you", "cells", "code_summary", "approved_stale", "draft_seen"}


def derive(it: dict, now: float) -> None:
    """Fields the status page shows, computed from the item file."""
    it["page"] = "index.html#i=" + it["id"]   # opens inside index.html, where the review server saves clicks
    needs = [[d.get("kind", "decision"), d.get("text", ""), d.get("since"), d.get("id")] for d in it.get("decisions", []) if not d.get("closed")]
    if it.get("draft"):
        needs.append(["proposed wording", f"A session proposed new wording ({', '.join(k for k in it['draft'] if k in ('title', 'why', 'answer'))})", it["draft"].get("at")])
    for c in it.get("code", []):
        c["promote"] = c.get("state") == "throwaway" and (len(c.get("used_by", [])) >= 2 or it.get("in_paper"))
        if c["promote"]:
            why = "used by more than one question" if len(c.get("used_by", [])) >= 2 else "its result is going into the paper"
            needs.append(["make permanent?", f"{c.get('what', 'code')} is a throwaway script, and {why}", None])
    for r in it.get("runs_status", []):
        if r["state"] == "waiting on Phil":
            needs.append(["run waiting on you", f"{r['label']} ({r.get('machine', '?')}): {r.get('summary', '')}", r.get("newest")])
    it["needs_you"] = needs
    g = it.get("grid") or {}
    cells = [c for grp in g.get("groups", []) for r in grp.get("rows", []) for c in r.get("cells", [])]
    if cells:
        it["cells"] = {"done": sum(c.get("state") in ("yes", "tie", "no") for c in cells),
                       "running": sum(c.get("state") in ("running", "waiting") for c in cells),
                       "not_run": sum(c.get("state") == "gap" for c in cells)}
    it["code_summary"] = " · ".join(f"{c.get('what', '')}: {c.get('state', '')}" for c in it.get("code", []))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--planning", default=PLANNING)
    ap.add_argument("--hosts", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--items", default=None, help="item folder (default: planning/dashboard/items)")
    args = ap.parse_args()
    plan = Path(args.planning)
    hosts_dir = Path(args.hosts or plan / "dashboard" / "hosts")
    out = Path(args.out or plan / "dashboard" / "index.html")
    now_dt = datetime.now(timezone.utc)
    now = now_dt.timestamp()

    briefs = {}
    for f in sorted((plan / "programs").glob("*.md")):
        if f.name.startswith("_") or "research-findings" in f.name:
            continue
        b = parse_brief(f)
        if b:
            briefs[b["slug"]] = b
    board_items = []
    for f in sorted((plan / "boards").glob("*.md")):
        if not f.name.startswith("_"):
            board_items += parse_board(f)
    for it in board_items:
        it["age"] = board_age_days(it["date"], now_dt)
        it["stale"] = it["age"] is not None and it["age"] > STALE_BOARD_DAYS and it["glyph"] not in "✅●"
        if it["program"] not in briefs:
            # board names a slug that isn't a brief file (e.g. vista-bench-v7-...); match by prefix
            cand = [s for s in briefs if it["program"].startswith(s) or s.startswith(it["program"])]
            it["program_resolved"] = cand[0] if cand else None
        else:
            it["program_resolved"] = it["program"]

    out.parent.mkdir(parents=True, exist_ok=True)
    hosts, sessions = [], []
    for f in sorted(hosts_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        age_min = (now - (epoch(d.get("written_at")) or 0)) / 60
        hosts.append({"host": d["host"], "written_at": d.get("written_at"), "age_min": round(age_min),
                      "machine": d.get("machine"),
                      "stale": age_min > HOST_STALE_MIN, "liveness_ok": d.get("liveness_ok"),
                      "n": len(d.get("sessions", []))})
        for s in d.get("sessions", []):
            s["bucket"] = bucket(s, now)
            s["program"] = link_program(s, briefs, board_items)
            sessions.append(s)

    for b in briefs.values():
        b["sessions"] = [s["id"] for s in sessions if s["program"] == b["slug"] and s["bucket"] != "parked"]
        b["board"] = [i for i in board_items if i["program_resolved"] == b["slug"]]
        fresh_board = any(i["age"] is not None and i["age"] <= STALE_BOARD_DAYS for i in b["board"])
        if b["road"] == "decided work left" and not b["sessions"] and not fresh_board:
            b["road"] = "stalled"  # open stages on paper, nothing moving
    unowned_board = [i for i in board_items if not i["program_resolved"]]

    # Questions and features: one JSON file each under dashboard/items/.
    items, files = [], {}
    items_dir = Path(args.items) if args.items else plan / "dashboard" / "items"
    for f in sorted(items_dir.glob("*.json")) if items_dir.exists() else []:
        try:
            it = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: skipping {f.name}: {e}")
            continue
        if not isinstance(it, dict) or not it.get("id") or not it.get("title"):
            print(f"warning: skipping {f.name}: no id or title")
            continue
        it["file_updated"] = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()
        items.append(it)
        files[it["id"]] = f
    live_site = out.parent.resolve() == (plan / "dashboard").resolve()
    acts = load_phil_actions(plan)
    changed = apply_phil_actions(items, files, acts) if live_site else []
    if live_site:
        pages.write_atomic(plan / "dashboard" / "phil-actions.json", json.dumps(acts, indent=1, ensure_ascii=False))
    ids = {it["id"] for it in items}
    for s in sessions:
        meta = "manager" in (s.get("name") or "").lower() or (s.get("intent") or "").strip().startswith("/manage") \
            or "dashboard" in (s.get("name") or "").lower()
        s["item"] = None if meta else attach(s, items, ids, plan)
    hosts_by_name = {h["host"]: h for h in hosts}
    for it in items:
        it["sessions"] = [s["id"] for s in sessions if s.get("item") == it["id"]]
        it["runs_status"] = [run_status(r, plan, now, hosts_by_name) for r in it.get("runs", [])]
        derive(it, now)
    edited = [it for it in items if it.get("approved") and it["approved"].get("wording") not in (None, pages.wording_hash(it))]
    for it in edited:
        it["approved_stale"] = True
    drafts = [it["title"] for it in items if not it.get("approved") or it.get("approved_stale")]
    for it in items:
        it["draft_seen"] = pages.draft_seen(it)

    # Problems: Phil's/sessions' list + the daily review's proposals + what the builder sees for itself.
    def load_list(name):
        f = plan / "dashboard" / name
        try:
            return json.loads(f.read_text()) if f.exists() else []
        except json.JSONDecodeError:
            return []
    auto = []
    for it in items:
        for r in it["runs_status"]:
            if r["state"] == "possibly died":
                auto.append(f"Run '{r['label']}' on {r.get('machine', '?')}: readback says running, nothing written for {r['age_h']} h, and no matching job on the machine. Died? ({it['title']})")
            if r["state"] == "failed":
                auto.append(f"Run '{r['label']}' on {r.get('machine', '?')} failed: {r.get('summary', '')} ({it['title']})")
        open_d = [d for d in it.get("decisions", []) if not d.get("closed")]
        last = max([epoch(it["file_updated"]) or 0] + [epoch(s.get("updated_at")) or 0 for s in sessions if s.get("item") == it["id"]])
        if open_d and now - last > 14 * 86400:
            auto.append(f"'{it['title']}' has {len(open_d)} open decision(s) and nothing has moved in {int((now - last) / 86400)} days.")
    for h in hosts:
        m = h.get("machine") or {}
        if m.get("gpus") and all(g["util"] < 5 for g in m["gpus"]) and not any(j.get("gpu") for j in m.get("jobs", [])):
            auto.append(f"{h['host']}: all {len(m['gpus'])} GPUs idle and no GPU job running.")
    for it in edited:
        auto.append(f"'{it['title']}': its wording changed after you approved it (a session edited a field you own). Re-approve it, or restore the approved wording.")
    unatt = [s["name"] for s in sessions if not s.get("item") and s["bucket"] in ("working", "waiting", "asked")]
    if unatt:
        auto.append(f"{len(unatt)} active session(s) not tied to any question or feature: {', '.join(unatt[:6])}.")
    if live_site:
        pages.write_atomic(plan / "dashboard" / "problems-auto.json", json.dumps(auto, indent=1, ensure_ascii=False))
    problems = auto + load_list("problems-proposed.json") + load_list("problems.json")

    # Pages: one per item (also embedded in index.html, so the served site saves comments) and one per method.
    gen = now_dt.strftime("%Y-%m-%d %H:%M UTC")
    ml = (Path(__file__).with_name("mount_links.js")).read_text()
    by_id = {it["id"]: it for it in items}
    by_sid = {s["id"]: s for s in sessions}
    item_html = {}
    for it in items:
        view = dict(it, runs=[{**r, "state_label": r["state"]} for r in it["runs_status"]])
        ss = [by_sid[i] for i in it["sessions"] if by_sid[i]["bucket"] != "parked"]
        item_html[it["id"]] = pages.item_body(view, by_id, ss, gen)
        pages.write_atomic(out.parent / (it["id"] + ".html"), pages.item_page(view, by_id, ss, acts["comments"].get(it["id"], {}), ml, gen))
    methods = sorted({m for it in items for m in it.get("methods", [])})
    for m in methods:
        pages.write_atomic(out.parent / f"method-{m}.html", pages.method_page(m, [it for it in items if m in it.get("methods", [])], ml, gen))

    data = {
        "generated_at": now_dt.isoformat(), "hosts": hosts, "sessions": sessions,
        "briefs": list(briefs.values()), "unowned_board": unowned_board,
        "stale_board_days": STALE_BOARD_DAYS, "items": items, "problems": problems,
        "drafts": drafts, "methods": methods, "item_html": item_html,
        "item_comments": acts["comments"], "item_css": pages.scoped_css(pages.CSS), "item_js": pages.JS,
    }
    ml = (Path(__file__).with_name("mount_links.js")).read_text()
    page = TEMPLATE.replace("__DATA__", json.dumps(data).replace("</", "<\\/")).replace("/*__MOUNT_LINKS__*/", ml)
    page = page.replace("__GENERATED__", html.escape(now_dt.strftime("%Y-%m-%d %H:%M UTC")))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name("." + out.name + ".tmp")
    tmp.write_text(page)
    os.replace(tmp, out)
    counts = {}
    for s in sessions:
        counts[s["bucket"]] = counts.get(s["bucket"], 0) + 1
    print(f"wrote {out}  sessions={len(sessions)} {counts}  items={len(items)} methods={len(methods)} problems={len(problems)}"
          f"  applied={changed or 'none'}")


TEMPLATE = (Path(__file__).with_name("dashboard_template.html")).read_text()

if __name__ == "__main__":
    main()
