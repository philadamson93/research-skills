"""Switch this VM off cleanly: final dashboard snapshot saying why, then shutdown. Optionally wait for a job first.

    python3 power_off.py --now --reason "training done, nothing else here"        # /vm-off
    python3 power_off.py --after-job train_v3.py --reason "..." &                  # /long-job, queued
    python3 power_off.py --after-pid 12345 --reason "..." --dry-run

Waiting: polls every 5 minutes until the job is gone, then until nothing else is busy on the box (no busy Claude
session other than ones that are only idle, no other long job of this user), up to --max-wait-h more hours; if the
box never goes quiet it does NOT switch off, and says so on the dashboard. A guest shutdown stops a GCE VM
(compute billing ends; disks stay). Never runs on shared boxes (weill). On phil-sllm-01 (the dashboard builder and
review server) it needs --builder-ok.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import snapshot_sessions as snap  # noqa: E402

SHARED = ("weill",)              # always-on machines other people use: never switch these off
BUILDER = ("phil-sllm-01",)      # builds the dashboard and serves review pages
QUEUE = snap.HOME / ".cache" / "work-dashboard.poweroff.json"   # the snapshot reports this while waiting
POLL_S = int(os.environ.get("WD_POLL_S", "300"))


def own_name() -> str:
    """The calling session's name, from its job folder, if it has one."""
    try:
        return json.loads((Path(os.environ["CLAUDE_JOB_DIR"]) / "state.json").read_text()).get("name") or ""
    except (KeyError, OSError, json.JSONDecodeError):
        return ""


def hosts_dir() -> Path:
    """Next to this script on the mount copy (bin/ -> ../hosts), else the default mount path."""
    if os.environ.get("WD_HOSTS_DIR"):   # tests
        return Path(os.environ["WD_HOSTS_DIR"])
    if HERE.name == "bin" and (HERE.parent / "hosts").is_dir():
        return HERE.parent / "hosts"
    return Path(snap.DEFAULT_OUT)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def job_alive(pattern: str) -> bool:
    out = subprocess.run(["ps", "-u", str(os.getuid()), "-o", "pid=,args="], capture_output=True, text=True).stdout
    me = os.getpid()
    return any(pattern in ln and int(ln.split(None, 1)[0]) != me and "power_off.py" not in ln
               for ln in out.splitlines() if ln.strip())


def still_busy(ignore: str | None) -> list[str]:
    """What else is running here: busy Claude sessions (not this one's caller if it is idle) and long jobs."""
    why = []
    agents = snap.live_agents() or {}
    me = os.environ.get("CLAUDE_CODE_SESSION_ID")   # the session calling /vm-off or /long-job is busy by definition
    busy = [a.get("name") or sid[:8] for sid, a in agents.items() if a.get("status") == "busy" and sid != me]
    if busy:
        why.append("busy session(s): " + ", ".join(busy[:5]))
    jobs = [j["cmd"] for j in snap.machine_state().get("jobs", []) if "power_off.py" not in j["cmd"]
            and not (ignore and ignore in j["cmd"])]
    if jobs:
        why.append("long job(s): " + "; ".join(c[:80] for c in jobs[:3]))
    return why


def write_snapshot(extra: dict) -> Path:
    """Take a normal snapshot, then add `extra` (powered_off / power_off_skipped) to it."""
    out = hosts_dir()
    subprocess.run([sys.executable, str(HERE / "snapshot_sessions.py"), "--out", str(out)], check=False,
                   capture_output=True, text=True, timeout=600)
    f = out / f"{socket.gethostname()}.json"
    d = json.loads(f.read_text()) if f.exists() else {"host": socket.gethostname(), "sessions": []}
    d.update(extra)
    tmp = out / f".{socket.gethostname()}.json.tmp"
    tmp.write_text(json.dumps(d, indent=1))
    os.replace(tmp, f)
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--now", action="store_true")
    g.add_argument("--after-pid", type=int)
    g.add_argument("--after-job", help="text in the job's process command; wait until no process matches")
    ap.add_argument("--reason", required=True, help="one plain sentence for the dashboard")
    ap.add_argument("--by", default=own_name(), help="session name, for the record")
    ap.add_argument("--max-wait-h", type=float, default=24, help="after the job ends, how long to wait for the box to go quiet")
    ap.add_argument("--builder-ok", action="store_true", help="allow switching off phil-sllm-01")
    ap.add_argument("--dry-run", action="store_true", help="do every step except the shutdown")
    a = ap.parse_args()

    host = socket.gethostname()
    if host.startswith(SHARED):
        print(f"ERROR: {host} is shared and always on; never switch it off (use start_snapshot.sh's stand-down instead).")
        return 2
    if host in BUILDER and not a.builder_ok:
        print(f"ERROR: {host} builds the dashboard and serves review pages; pass --builder-ok if Phil said to switch it off.")
        return 2

    waiting_for = f"pid {a.after_pid}" if a.after_pid else a.after_job
    if waiting_for:
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE.write_text(json.dumps({"after": waiting_for, "reason": a.reason, "by": a.by,
                                     "since": datetime.now(timezone.utc).isoformat()}))
        print(f"{host}: waiting for {waiting_for} to finish, then switching off")
        while (pid_alive(a.after_pid) if a.after_pid else job_alive(a.after_job)):
            time.sleep(POLL_S)
        deadline = time.time() + a.max_wait_h * 3600
        while (busy := still_busy(a.after_job)) and time.time() < deadline:
            print(f"{host}: job finished; still running here: {'; '.join(busy)} — waiting")
            time.sleep(POLL_S)
        if busy:
            QUEUE.unlink(missing_ok=True)
            f = write_snapshot({"power_off_skipped": {"at": datetime.now(timezone.utc).isoformat(), "reason": a.reason,
                                                      "still_running": busy}})
            print(f"{host}: NOT switching off — still running after {a.max_wait_h} h: {'; '.join(busy)} ({f})")
            return 1
    else:
        busy = still_busy(None)
        if busy:
            print(f"{host}: still running here: {'; '.join(busy)}")
            print("Refusing --now while something else is running; wait for it, or queue with --after-job.")
            return 1

    QUEUE.unlink(missing_ok=True)
    rec = {"at": datetime.now(timezone.utc).isoformat(), "reason": a.reason, "by": a.by,
           "after": waiting_for, "dry_run": a.dry_run}
    f = write_snapshot({"powered_off": rec})
    print(f"{host}: final snapshot written ({f}) — {a.reason}")
    if a.dry_run:
        print("dry run: not shutting down")
        return 0
    subprocess.run(["sudo", "-n", "shutdown", "-h", "+1", f"work dashboard: {a.reason}"], check=False)
    print(f"{host}: shutting down in 1 minute (cancel: sudo shutdown -c)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
