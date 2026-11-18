#!/usr/bin/env python3
"""Write this machine's Claude Code sessions to the mount, for the work dashboard.

Run on every machine that hosts sessions (sllm-01, sllm-02, the hcpu boxes, the Mac).
Reads only local files and `claude agents --json`; never messages a session.

    python3 snapshot_sessions.py [--days 7] [--out <planning>/dashboard/hosts]

Output: one JSON file per host, `<out>/<hostname>.json`, replaced atomically.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
JOBS = HOME / ".claude" / "jobs"
PROJECTS = HOME / ".claude" / "projects"
DEFAULT_OUT = "/mnt/su-vista-uscentral1/chaudhari_lab/phil/planning/dashboard/hosts"
# Explorer app runs spawn throwaway interactive sessions; they are not fleet work.
SKIP_CWD = re.compile(r"/\.vista-explorer")
TAIL_BYTES = 4_000_000
MOUNT_PATH = re.compile(r"(/mnt/su-vista-uscentral1/[^\s`'\")\]<>,;|]+)")


def iso_to_epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def live_agents() -> dict[str, dict]:
    """sessionId -> row from `claude agents --json` (the authority on liveness)."""
    try:
        out = subprocess.run(
            ["claude", "agents", "--json"], capture_output=True, text=True, timeout=90
        ).stdout
        return {a["sessionId"]: a for a in json.loads(out) if a.get("sessionId")}
    except Exception as e:  # noqa: BLE001 - a missing CLI just means no liveness column
        print(f"warning: claude agents --json failed: {e}")
        return {}


def find_transcript(session_id: str, hint: str | None) -> Path | None:
    if hint and Path(hint).exists():
        return Path(hint)
    hits = glob.glob(str(PROJECTS / "*" / f"{session_id}.jsonl"))
    return Path(hits[0]) if hits else None


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text"
        )
    return ""


def read_transcript_tail(path: Path) -> dict:
    """Newest cwd/branch, last assistant text, last human prompt."""
    info: dict = {}
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - TAIL_BYTES))
            raw = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return info
    if size > TAIL_BYTES:
        raw = raw[1:]  # first line is probably cut
    for line in raw:
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("cwd"):
            info["cwd"] = o["cwd"]
            info["branch"] = o.get("gitBranch")
        t = o.get("type")
        if t == "assistant":
            txt = text_of(o.get("message", {}).get("content"))
            if txt.strip():
                info["last_text"] = txt
                info["last_text_at"] = o.get("timestamp")
        elif t == "user" and not o.get("isMeta") and not o.get("toolUseResult"):
            txt = text_of(o.get("message", {}).get("content"))
            if txt.strip() and not txt.lstrip().startswith("<"):
                info["last_prompt"] = txt.strip()[:400]
                info["last_prompt_at"] = o.get("timestamp")
    return info


def section(text: str, heading: str) -> list[str]:
    """Bullets under a bold or markdown heading like **Next** or ## Next."""
    m = re.search(
        rf"(?im)^\s*(?:\*\*|#+\s*){re.escape(heading)}[^\n]*\n((?:[ \t]*[-*\d].*\n?)+)", text
    )
    if not m:
        return []
    return [re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", b).strip() for b in m.group(1).splitlines() if b.strip()][:6]


def parse_last_text(text: str) -> dict:
    """Pull the fixed-format lines sessions already write at the end of a chunk."""
    p: dict = {}
    for key, pat in {
        "result": r"(?im)^result:\s*(.+)$",
        "needs_input": r"(?im)^needs input:\s*(.+)$",
        "failed": r"(?im)^failed:\s*(.+)$",
    }.items():
        hits = re.findall(pat, text)
        if hits:
            p[key] = hits[-1].strip()
    # Close-out block: Program / Done / Verified / Next / Yours
    for label in ("Program", "Done", "Verified", "Next", "Yours"):
        hits = re.findall(rf"(?m)^\s*{label}\s{{2,}}(.+)$", text)
        if hits:
            p[f"close_{label.lower()}"] = hits[-1].strip()
    # Resume block from /wrapup
    m = re.findall(r"(?im)^\s*(?:ITEM\s+|\**Item\**:\s*)\S*?items/([\w.-]+)\.json", text) or \
        re.findall(r"(?im)^\s*\**Item\**:\s*([a-z0-9][\w.-]+)\b", text)
    if m:
        p["item"] = m[-1]
    for label in ("PROGRAM", "BRIEF", "REPO", "BRANCH", "DOC"):
        hits = re.findall(rf"(?m)^\s*{label}\s+(.+)$", text)
        if hits:
            p[f"resume_{label.lower()}"] = hits[-1].strip()
    m = re.search(r"(?m)^\s*Resume ▸\s*(.+)$", text)
    if m:
        p["resume_title"] = m.group(1).strip()
    p["next"] = section(text, "Next")
    p["blocked_on_user"] = section(text, "Blocked on user")
    paths = []
    for x in MOUNT_PATH.findall(text):
        x = x.rstrip(".:*")
        if x not in paths:
            paths.append(x)
    p["mount_paths"] = paths[:8]
    return p


def timeline_events(job_dir: Path, since: float) -> list[dict]:
    out = []
    tl = job_dir / "timeline.jsonl"
    if not tl.exists():
        return out
    prev = None
    for line in tl.read_text(errors="replace").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        at = iso_to_epoch(o.get("at"))
        st = o.get("state")
        # Keep transitions into done / blocked / failed: the moments Phil cares about.
        if at and at >= since and st in ("done", "blocked", "failed") and st != prev:
            out.append({"at": o["at"], "state": st, "detail": (o.get("detail") or "")[:300]})
        prev = st
    return out[-12:]


def machine_state() -> dict:
    """What this box is doing besides Claude: GPUs, long-running jobs of this user, load, disk."""
    m: dict = {"cores": os.cpu_count(), "load": [round(x, 1) for x in os.getloadavg()]}
    try:
        st = os.statvfs(str(HOME))
        m["home_free_gb"] = round(st.f_bavail * st.f_frsize / 1e9)
    except OSError:
        pass
    try:
        q = subprocess.run(["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20)
        m["gpus"] = [dict(zip(("i", "util", "mem_used", "mem_total"), map(int, map(str.strip, l.split(",")))))
                     for l in q.stdout.splitlines() if l.strip()]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        m["gpus"] = None  # no GPU on this box
    gpu_pids: set[int] = set()
    if m["gpus"] is not None:
        try:
            q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                               capture_output=True, text=True, timeout=20)
            gpu_pids = {int(x) for x in q.stdout.split() if x.strip().isdigit()}
        except (OSError, subprocess.TimeoutExpired):
            pass
    jobs = []
    procs = []   # every long-lived process, for matching a run's job name (agent runs often sit at low CPU)
    try:
        out = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "pid=,etimes=,pcpu=,pmem=,args="],
                             capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue
            pid, et, cpu, mem, args = parts
            et, cpu = int(et), float(cpu)
            if et >= 1800 and len(procs) < 400:
                procs.append(args[:200])
            # long-running and busy, and not Claude / shells / editors themselves
            on_gpu = int(pid) in gpu_pids
            if et < 1800 or (cpu < 20 and not on_gpu) or re.search(r"(^|/)(claude|node|bash|zsh|sshd|tmux|ps|top|htop)( |$)", args):
                continue
            try:
                cwd = os.readlink(f"/proc/{pid}/cwd")
            except OSError:
                cwd = None
            jobs.append({"pid": int(pid), "hours": round(et / 3600, 1), "cpu": cpu, "mem": float(mem),
                         "cmd": args[:200], "cwd": cwd, "gpu": on_gpu})
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    m["jobs"] = sorted(jobs, key=lambda j: -j["cpu"])[:12]   # busy ones, for display
    m["procs"] = procs
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=7, help="include sessions touched in this window")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    host = socket.gethostname()
    now = time.time()
    since = now - args.days * 86400
    agents = live_agents()
    sessions: dict[str, dict] = {}

    for sj in JOBS.glob("*/state.json"):
        try:
            s = json.loads(sj.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        sid = s.get("sessionId")
        upd = iso_to_epoch(s.get("updatedAt")) or sj.stat().st_mtime
        if upd < since and sid not in agents:
            continue
        a = agents.get(sid, {})
        rec = {
            "id": sj.parent.name,
            "session_id": sid,
            "host": host,
            "kind": "background",
            "name": s.get("name") or sj.parent.name,
            "intent": (s.get("intent") or "")[:600],
            "job_state": s.get("state"),
            "tempo": s.get("tempo"),
            "live": a.get("status") if a else "gone",
            "detail": (s.get("detail") or "")[:300],
            "result": (s.get("output") or {}).get("result") if isinstance(s.get("output"), dict) else None,
            "needs": (s.get("needs") or "")[:800] or None,
            "created_at": s.get("createdAt"),
            "updated_at": s.get("updatedAt"),
            "tokens": s.get("tokens"),
            "events": timeline_events(sj.parent, now - 72 * 3600),
            "artifacts": [c.get("href") for c in (s.get("children") or []) if isinstance(c, dict) and c.get("href")],
        }
        tp = find_transcript(sid, s.get("linkScanPath")) if sid else None
        if tp:
            rec.update(read_transcript_tail(tp))
        sessions[sid or rec["id"]] = rec

    # Interactive terminal sessions have no job folder; take them from the live list.
    for sid, a in agents.items():
        if sid in sessions or SKIP_CWD.search(a.get("cwd", "")):
            continue
        rec = {
            "id": a.get("id") or sid[:8],
            "session_id": sid,
            "host": host,
            "kind": a.get("kind", "interactive"),
            "name": a.get("name") or sid[:8],
            "live": a.get("status"),
            "cwd": a.get("cwd"),
            "events": [],
        }
        tp = find_transcript(sid, None)
        if tp:
            rec.update(read_transcript_tail(tp))
            rec["updated_at"] = datetime.fromtimestamp(tp.stat().st_mtime, timezone.utc).isoformat()
        sessions[sid] = rec

    for rec in sessions.values():
        txt = rec.pop("last_text", "") or ""
        rec["last_text_tail"] = txt[-1500:]
        rec["parsed"] = parse_last_text(txt)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "host": host,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "liveness_ok": bool(agents),
        "machine": machine_state(),
        "sessions": sorted(sessions.values(), key=lambda r: r.get("updated_at") or "", reverse=True),
    }
    tmp = out_dir / f".{host}.json.tmp"
    tmp.write_text(json.dumps(payload, indent=1))
    os.replace(tmp, out_dir / f"{host}.json")
    print(f"{host}: {len(sessions)} sessions -> {out_dir / (host + '.json')}")


if __name__ == "__main__":
    main()
