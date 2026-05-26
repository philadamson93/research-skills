#!/usr/bin/env python3
"""
explain-plan-relay.py

Tiny localhost HTTP relay that bridges drill-down clicks in an explain-plan HTML
to a headless `claude -p` invocation. Lets the static HTML render Claude's answer
inline in its drill panel without the user copy-pasting.

Usage
-----
    python explain-plan-relay.py [--port 7237] [--cmd claude]

Then double-click any drillable node in an explain-plan HTML. The HTML's drill
panel will fetch this relay and render the response. If the relay isn't running,
the HTML falls back gracefully to the clipboard flow.

Security
--------
- Binds to 127.0.0.1 only (never 0.0.0.0).
- No auth — relies on loopback isolation.
- Sets permissive CORS so `file://` HTMLs can fetch it.
- Sandbox: arbitrary text from any local browser will be passed to `claude -p`.
  Don't open untrusted HTML files in the same browser while this is running.

Protocol
--------
POST / with JSON body:
    {
      "prompt": "<full drill prompt string>",
      "cwd":    "<absolute path to the repo root for claude -p to run in>",
      "timeout": 300                          # optional, seconds, default 300
    }

Response (200):
    {
      "answer": "<stdout from claude -p>",
      "stderr": "<stderr if any>",
      "elapsed_s": 12.4
    }

Errors:
    400 — malformed JSON or missing fields
    500 — claude -p exited non-zero (stderr in body)
    504 — claude -p timed out
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CLAUDE_CMD = "claude"  # overridden by --cmd


class Handler(BaseHTTPRequestHandler):
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, body: dict) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write(f"[relay {self.log_date_time_string()}] {fmt % args}\n")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # Health probe so the HTML can detect whether the relay is up before
        # offering "fetch" affordance.
        self._json(200, {"status": "ok", "cmd": CLAUDE_CMD})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._json(400, {"error": "empty body"})
            return
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as e:
            self._json(400, {"error": f"bad json: {e}"})
            return

        prompt = body.get("prompt")
        cwd = body.get("cwd")
        timeout = int(body.get("timeout", 300))
        if not isinstance(prompt, str) or not prompt.strip():
            self._json(400, {"error": "missing 'prompt'"})
            return
        if cwd is not None and not isinstance(cwd, str):
            self._json(400, {"error": "'cwd' must be a string"})
            return

        sys.stderr.write(
            f"[relay] dispatching prompt ({len(prompt)} chars, cwd={cwd!r}, timeout={timeout}s)\n"
        )
        t0 = time.monotonic()
        try:
            res = subprocess.run(  # noqa: S603 — local user-initiated only
                [CLAUDE_CMD, "-p", prompt],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            self._json(500, {"error": f"`{CLAUDE_CMD}` not found on PATH"})
            return
        except subprocess.TimeoutExpired:
            self._json(504, {"error": f"timed out after {timeout}s"})
            return
        elapsed = round(time.monotonic() - t0, 2)

        if res.returncode != 0:
            self._json(500, {
                "error": f"claude -p exited {res.returncode}",
                "stderr": res.stderr,
                "elapsed_s": elapsed,
            })
            return

        self._json(200, {
            "answer": res.stdout,
            "stderr": res.stderr,
            "elapsed_s": elapsed,
        })


def main() -> None:
    global CLAUDE_CMD
    parser = argparse.ArgumentParser(description="explain-plan drill-down relay")
    parser.add_argument("--port", type=int, default=7237)
    parser.add_argument("--cmd", default="claude", help="Claude CLI binary (default: claude)")
    args = parser.parse_args()

    CLAUDE_CMD = args.cmd

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    sys.stderr.write(
        f"explain-plan relay listening on http://127.0.0.1:{args.port}\n"
        f"  CLI: {CLAUDE_CMD}\n"
        f"  Ctrl-C to stop.\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nshutdown\n")


if __name__ == "__main__":
    main()
