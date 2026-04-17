"""
Local SSE server for the Context Recovery dashboard.

Two modes:
  - replay (default): reads results/recovery_comparison.json and streams the
    saved metrics with synthesised tick-by-tick progress so the dashboard
    looks like a live benchmark run.
  - live: spawns runner.py with `all` and forwards every `[EVENT] {...}` line
    it prints on stdout as a single SSE message.

The server has no third-party dependencies — only the Python stdlib.

Usage:
    python3 server.py [--port 8765]

Then open http://localhost:8765/ in a browser. The dashboard chooses the
mode itself via the `?live=1` query string when it opens the SSE stream.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DIR = Path(__file__).resolve().parent
RESULTS_FILE = DIR / "results" / "recovery_comparison.json"
DASHBOARD_FILE = DIR / "dashboard_recovery.html"

ORDER = ["md_files", "github_issues", "mem0", "helixir_mcp"]


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    # Silence default access log spam.
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):  # noqa: N802 - http.server contract
        url = urlparse(self.path)
        if url.path in ("/", "/dashboard", "/index.html"):
            self._serve_html()
        elif url.path == "/events":
            qs = parse_qs(url.query)
            mode = "live" if qs.get("live", ["0"])[0] == "1" else "replay"
            self._serve_events(mode)
        elif url.path == "/health":
            self._serve_text(200, "ok")
        else:
            self._serve_text(404, "not found")

    # ---------- handlers ----------

    def _serve_html(self):
        try:
            body = DASHBOARD_FILE.read_bytes()
        except OSError as exc:
            self._serve_text(500, f"dashboard read failed: {exc}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_text(self, code: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_events(self, mode: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            if mode == "live":
                self._stream_live()
            else:
                self._stream_replay()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client closed tab

    def _emit(self, payload: dict):
        self.wfile.write(_sse(payload))
        self.wfile.flush()

    # ---------- replay ----------

    def _stream_replay(self):
        if not RESULTS_FILE.exists():
            self._emit({
                "type": "error",
                "message": f"replay data not found: {RESULTS_FILE.name} — "
                           "run with ?live=1 once to record it",
            })
            return

        try:
            data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            self._emit({"type": "error", "message": f"replay JSON invalid: {exc}"})
            return

        approaches = data.get("approaches", {})
        meta = {
            "type": "start",
            "mode": "replay",
            "order": ORDER,
            "source": data.get("_source", "results/recovery_comparison.json"),
            "timestamp": data.get("timestamp"),
        }
        self._emit(meta)

        for key in ORDER:
            if key not in approaches:
                continue
            metrics = approaches[key]
            self._replay_one(key, metrics)

        self._emit({"type": "complete", "mode": "replay"})

    def _replay_one(self, approach: str, metrics: dict):
        """Animate one approach's run over a synthesised wall-clock window."""
        tokens = int(metrics.get("total_tokens", 0))
        time_ms = int(metrics.get("total_time_ms", 0))
        accuracy = float(metrics.get("accuracy_pct", 0))
        tool_calls = int(metrics.get("tool_calls", 0))

        # Compress real wall-clock into a stage-friendly window.
        # Heuristic: clamp between 2.0s and 6.0s per approach.
        wall_seconds = max(2.0, min(6.0, time_ms / 1000.0 / 4.0))
        steps = 24
        step_dt = wall_seconds / steps

        self._emit({
            "type": "approach_start",
            "approach": approach,
            "tool_calls": tool_calls,
        })

        for i in range(1, steps + 1):
            frac = i / steps
            self._emit({
                "type": "approach_progress",
                "approach": approach,
                "tokens": int(tokens * frac),
                "time_ms": int(time_ms * frac),
                "tool_calls_done": int(tool_calls * frac),
            })
            time.sleep(step_dt)

        self._emit({
            "type": "approach_complete",
            "approach": approach,
            "metrics": metrics,
        })

    # ---------- live ----------

    def _stream_live(self):
        runner = DIR / "runner.py"
        if not runner.exists():
            self._emit({"type": "error", "message": "runner.py not found"})
            return

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["RECOVERY_EMIT_EVENTS"] = "1"

        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(runner), "all"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(DIR),
                env=env,
                text=True,
            )
        except OSError as exc:
            self._emit({"type": "error", "message": f"failed to spawn runner: {exc}"})
            return

        self._emit({"type": "start", "mode": "live", "order": ORDER})

        # Heartbeat thread keeps the connection from idling out while the
        # runner is busy doing a slow LLM call between events.
        stop_hb = threading.Event()

        def heartbeat():
            while not stop_hb.is_set():
                time.sleep(5)
                try:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                except Exception:
                    return

        hb = threading.Thread(target=heartbeat, daemon=True)
        hb.start()

        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if line.startswith("[EVENT] "):
                    try:
                        self._emit(json.loads(line[len("[EVENT] "):]))
                    except json.JSONDecodeError:
                        self._emit({"type": "log", "line": line})
                elif line.strip():
                    self._emit({"type": "log", "line": line})
        finally:
            stop_hb.set()

        rc = proc.wait()
        self._emit({"type": "complete", "mode": "live", "exit_code": rc})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard: http://{args.host}:{args.port}/")
    print(f"  replay (default): http://{args.host}:{args.port}/")
    print(f"  live mode toggled in the UI via the 'refresh_bench' checkbox")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown")


if __name__ == "__main__":
    main()
