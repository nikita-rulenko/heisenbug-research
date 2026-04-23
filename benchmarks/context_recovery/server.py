"""
Local SSE server for the Context Recovery dashboard.

Modes:
  - replay (default): plays back results/runs/baseline.jsonl with the same
    intra-approach timing the live run had (between-approach idle gaps are
    compressed to ~50 ms).
  - replay by id (?replay=<filename>): same as default but for any recording
    the user picked from the dashboard select.
  - live (?live=1): spawns runner.py and forwards every `[EVENT]` line; in
    parallel it appends each event to results/runs/{ISO}.jsonl + writes a
    .meta.json sidecar so /runs can list it without parsing the full log.

Routes:
  GET  /                  → dashboard HTML
  GET  /runs              → JSON list of recordings (id, timestamp, summary)
  GET  /events            → SSE replay of baseline.jsonl
  GET  /events?live=1     → SSE live run (also records to disk)
  GET  /events?replay=<id>→ SSE replay of a specific recording
  GET  /api/key-status    → {has_key: bool} — does .env contain CEREBRAS_API_KEY
  POST /api/save-keys     → body {cerebras_api_key}, validates with Cerebras, writes .env
  GET  /health            → "ok"

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DIR = Path(__file__).resolve().parent
RESULTS_FILE = DIR / "results" / "recovery_comparison.json"
RUNS_DIR = DIR / "results" / "runs"
BASELINE_ID = "baseline"
# Project root .env wins; fall back to a benchmark-local one if both exist
# (saving via the modal always writes to whichever path the user already has).
REPO_ROOT = DIR.parent.parent
ENV_FILE_CANDIDATES = [REPO_ROOT / ".env", DIR / ".env"]
DASHBOARD_FILE = DIR / "dashboard_recovery.html"
DASHBOARD_V2_FILE = DIR / "dashboard_recovery_v2.html"

ORDER = ["md_files", "github_issues", "mem0", "helixir_mcp"]

# Idle gap between `approach_complete[k]` and `approach_start[k+1]` in
# replay — the live server has multi-second idle here (subprocess setup,
# Helixir restart) which carries no information for the audience.
INTER_APPROACH_GAP_MS = 50

# Shared handle to the currently-running runner subprocess, so /stop can
# terminate it even if TCP-level disconnect detection is slow.
_active_proc_lock = threading.Lock()
_active_proc: subprocess.Popen | None = None


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _load_dotenv() -> None:
    """Minimal .env loader — sets os.environ for keys not already present.

    Reads every candidate path so a repo-root .env still works when the
    benchmark dir doesn't have its own.
    """
    for path in ENV_FILE_CANDIDATES:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def _writable_env_path() -> Path:
    """Where /api/save-keys writes — prefer an existing file, else repo root."""
    for path in ENV_FILE_CANDIDATES:
        if path.exists():
            return path
    return ENV_FILE_CANDIDATES[0]


def _has_cerebras_key() -> bool:
    return bool(os.environ.get("CEREBRAS_API_KEY", "").strip())


def _validate_cerebras_key(key: str) -> tuple[bool, str]:
    """Sanity check: tiny chat.completions call — same surface the runner uses.

    Uses httpx (via runner.py's dep) so TLS fingerprint + User-Agent match what
    the actual benchmark sends. Plain urllib trips Cloudflare error 1010 on
    api.cerebras.ai regardless of auth.
    """
    payload = {
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "temperature": 0,
    }
    try:
        import httpx  # runner.py already depends on this
    except ImportError:
        return False, "httpx not installed — run `pip install httpx`"

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if 200 <= resp.status_code < 300:
        return True, "ok"

    body = resp.text[:300] if resp.text else ""
    detail = body
    try:
        j = resp.json()
        detail = (j.get("error") or {}).get("message") or j.get("message") or body
    except Exception:
        pass
    sys.stderr.write(f"[cerebras-validate] HTTP {resp.status_code} body={body!r}\n")

    code = resp.status_code
    if code == 401:
        return False, f"unauthorized (401): {detail or 'invalid key'}"
    if code == 403:
        return False, f"forbidden (403): {detail or 'key blocked / scope mismatch'}"
    if code == 404:
        return False, "model gpt-oss-120b not available on this key"
    return False, f"HTTP {code}{': ' + detail if detail else ''}"


_KEY_LINE_RE = re.compile(r"^CEREBRAS_API_KEY\s*=.*$", re.MULTILINE)


def _save_cerebras_key(key: str) -> None:
    """Write/replace CEREBRAS_API_KEY in .env, preserving other lines."""
    env_path = _writable_env_path()
    body = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    line = f'CEREBRAS_API_KEY="{key}"'
    if _KEY_LINE_RE.search(body):
        body = _KEY_LINE_RE.sub(line, body)
    else:
        if body and not body.endswith("\n"):
            body += "\n"
        body += line + "\n"
    env_path.write_text(body, encoding="utf-8")
    os.environ["CEREBRAS_API_KEY"] = key


# ─────────────────────────────────────────────────────────────────────────
# Recordings
# ─────────────────────────────────────────────────────────────────────────


def _safe_id(name: str) -> str:
    """Sanitise a recording id so it can't escape RUNS_DIR."""
    return re.sub(r"[^A-Za-z0-9_\-]", "", name)[:64]


def _recording_paths(rid: str) -> tuple[Path, Path]:
    rid = _safe_id(rid) or BASELINE_ID
    return RUNS_DIR / f"{rid}.jsonl", RUNS_DIR / f"{rid}.meta.json"


def _list_recordings() -> list[dict]:
    if not RUNS_DIR.exists():
        return []
    items: list[dict] = []
    for meta_path in sorted(RUNS_DIR.glob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Python 3.8 compat (no str.removesuffix): meta_path.name is "<id>.meta.json"
        rid = meta_path.name[:-len(".meta.json")]
        if not (RUNS_DIR / f"{rid}.jsonl").exists():
            continue
        items.append({
            "id": rid,
            "timestamp": meta.get("timestamp"),
            "duration_ms": meta.get("duration_ms"),
            "approaches": meta.get("approaches", {}),
            "label": meta.get("label", rid),
        })
    # Pinned baseline first if present, then most recent
    items.sort(key=lambda x: (x["id"] != BASELINE_ID, x.get("timestamp") or ""))
    return items


def _build_meta(events: list[dict]) -> dict:
    """Summarise a recording (used for the picker label)."""
    summary: dict[str, dict] = {}
    duration = 0
    timestamp = None
    for evt in events:
        if evt.get("type") == "approach_complete" and "metrics" in evt:
            summary[evt["approach"]] = {
                "accuracy_pct": evt["metrics"].get("accuracy_pct"),
                "total_tokens": evt["metrics"].get("total_tokens"),
                "total_time_ms": evt["metrics"].get("total_time_ms"),
            }
        if evt.get("type") == "start" and evt.get("timestamp"):
            timestamp = evt["timestamp"]
        ts = evt.get("ts_ms")
        if isinstance(ts, int):
            duration = max(duration, ts)
    return {
        "timestamp": timestamp,
        "duration_ms": duration,
        "approaches": summary,
    }


# ─────────────────────────────────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────────────────────────────────


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    # ---------- routing ----------

    def do_GET(self):  # noqa: N802 - http.server contract
        url = urlparse(self.path)
        if url.path in ("/", "/dashboard", "/index.html"):
            self._serve_html()
        elif url.path in ("/v2", "/dashboard/v2", "/index_v2.html"):
            self._serve_html_v2()
        elif url.path == "/events":
            qs = parse_qs(url.query)
            if qs.get("live", ["0"])[0] == "1":
                self._serve_events_live()
            else:
                # Clamp replay speed to a sane window. 1.0 = recorded pace,
                # 2.0 = demo pace (fits better in a conference slot).
                try:
                    speed = float(qs.get("speed", ["1"])[0])
                except (TypeError, ValueError):
                    speed = 1.0
                speed = max(0.25, min(8.0, speed))
                rid = qs["replay"][0] if "replay" in qs else BASELINE_ID
                self._serve_events_replay(rid, speed=speed)
        elif url.path == "/runs":
            self._serve_json(200, {"runs": _list_recordings(), "default": BASELINE_ID})
        elif url.path == "/api/key-status":
            self._serve_json(200, {"has_key": _has_cerebras_key()})
        elif url.path == "/stop":
            self._handle_stop()
        elif url.path == "/health":
            self._serve_text(200, "ok")
        else:
            self._serve_text(404, "not found")

    def do_POST(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/save-keys":
            self._handle_save_keys()
        else:
            self._serve_text(404, "not found")

    # ---------- low-level write helpers ----------

    def _serve_html(self):
        self._serve_file(DASHBOARD_FILE)

    def _serve_html_v2(self):
        self._serve_file(DASHBOARD_V2_FILE)

    def _serve_file(self, path: Path):
        try:
            body = path.read_bytes()
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

    def _serve_json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _begin_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _emit(self, payload: dict):
        self.wfile.write(_sse(payload))
        self.wfile.flush()

    # ---------- stop ----------

    def _handle_stop(self):
        global _active_proc
        killed = False
        with _active_proc_lock:
            proc = _active_proc
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    killed = True
                except Exception:
                    pass
        self._serve_json(200, {"stopped": killed})

    # ---------- key management ----------

    def _handle_save_keys(self):
        length = int(self.headers.get("Content-Length") or "0")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._serve_json(400, {"ok": False, "error": "invalid JSON body"})
            return
        key = (body.get("cerebras_api_key") or "").strip()
        force = bool(body.get("force"))
        if not key:
            self._serve_json(400, {"ok": False, "error": "cerebras_api_key required"})
            return
        if not force:
            ok, msg = _validate_cerebras_key(key)
            if not ok:
                # Surface the raw Cerebras response; caller can retry with force=true
                self._serve_json(200, {"ok": False, "error": msg, "can_force": True})
                return
        try:
            _save_cerebras_key(key)
        except OSError as exc:
            self._serve_json(500, {"ok": False, "error": f"write .env failed: {exc}"})
            return
        self._serve_json(200, {"ok": True, "forced": force})

    # ---------- replay ----------

    def _serve_events_replay(self, rid: str, speed: float = 1.0):
        self._begin_sse()
        try:
            self._stream_replay(rid, speed=speed)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _stream_replay(self, rid: str, speed: float = 1.0):
        jsonl, _ = _recording_paths(rid)

        if not jsonl.exists():
            # Fallback to legacy synthetic replay from comparison JSON,
            # so the dashboard still shows something on a fresh checkout.
            if rid == BASELINE_ID and RESULTS_FILE.exists():
                self._stream_legacy_replay(speed=speed)
                return
            self._emit({"type": "error", "message": f"recording not found: {rid}"})
            return

        events: list[dict] = []
        for raw in jsonl.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            self._emit({"type": "error", "message": f"empty recording: {rid}"})
            return

        # Replace the start event with a replay-flagged copy so the dashboard
        # knows it's playback (still mode=replay; live status pill disabled).
        first = dict(events[0])
        first["mode"] = "replay"
        first["recording_id"] = rid
        first["order"] = first.get("order", ORDER)
        self._emit(first)

        prev_ts = events[0].get("ts_ms", 0)
        prev_type = events[0].get("type")
        prev_approach = events[0].get("approach")

        for evt in events[1:]:
            ts = evt.get("ts_ms", prev_ts)
            real_delta = max(0, ts - prev_ts)

            # Compress idle between approaches.
            is_inter_approach = (
                evt.get("type") == "approach_start"
                and prev_type == "approach_complete"
            )
            delta_ms = INTER_APPROACH_GAP_MS if is_inter_approach else real_delta

            # Cap any single delta to 8s — protects against unbounded hangs
            # captured in the recording (rare, but possible if a model stalled).
            delta_ms = min(delta_ms, 8000)

            if delta_ms > 0:
                time.sleep((delta_ms / 1000.0) / speed)

            self._emit(evt)
            prev_ts = ts
            prev_type = evt.get("type")
            prev_approach = evt.get("approach", prev_approach)

    def _stream_legacy_replay(self, speed: float = 1.0):
        """Pre-recording fallback: synthesise progress from the comparison JSON."""
        try:
            data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            self._emit({"type": "error", "message": f"replay JSON invalid: {exc}"})
            return

        approaches = data.get("approaches", {})
        self._emit({
            "type": "start",
            "mode": "replay",
            "order": ORDER,
            "source": data.get("_source", "results/recovery_comparison.json"),
            "timestamp": data.get("timestamp"),
        })

        for key in ORDER:
            if key not in approaches:
                continue
            metrics = approaches[key]
            tokens = int(metrics.get("total_tokens", 0))
            time_ms = int(metrics.get("total_time_ms", 0))
            tool_calls = int(metrics.get("tool_calls", 0))
            self._emit({"type": "approach_start", "approach": key,
                        "tool_calls": tool_calls})
            steps = max(8, time_ms // 80)
            step_dt = (time_ms / 1000.0) / max(steps, 1)
            for i in range(1, steps + 1):
                frac = i / steps
                self._emit({
                    "type": "approach_progress",
                    "approach": key,
                    "tokens": int(tokens * frac),
                    "time_ms": int(time_ms * frac),
                    "tool_calls_done": int(tool_calls * frac),
                })
                time.sleep(step_dt / speed)
            self._emit({"type": "approach_complete", "approach": key,
                        "metrics": metrics})

        self._emit({"type": "complete", "mode": "replay"})

    # ---------- live ----------

    def _serve_events_live(self):
        self._begin_sse()
        try:
            self._stream_live()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _stream_live(self):
        if not _has_cerebras_key():
            self._emit({
                "type": "need_keys",
                "missing": ["CEREBRAS_API_KEY"],
                "links": {
                    "cerebras": "https://cerebras.ai/inference",
                },
            })
            return

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

        global _active_proc
        with _active_proc_lock:
            _active_proc = proc

        # Recording: ISO-like id, written line-by-line so a kill mid-run
        # still leaves a partial-but-readable file.
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        rid = time.strftime("%Y-%m-%d_%H-%M-%S")
        jsonl_path, meta_path = _recording_paths(rid)
        recording: list[dict] = []
        rec_fp = jsonl_path.open("w", encoding="utf-8")

        start_evt = {
            "type": "start",
            "mode": "live",
            "order": ORDER,
            "recording_id": rid,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ts_ms": 0,
        }
        self._emit(start_evt)
        rec_fp.write(json.dumps(start_evt) + "\n")
        rec_fp.flush()
        recording.append(start_evt)

        # Heartbeat keeps the SSE connection alive during slow LLM gaps.
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

        client_gone = False
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                if line.startswith("[EVENT] "):
                    try:
                        evt = json.loads(line[len("[EVENT] "):])
                    except json.JSONDecodeError:
                        evt = {"type": "log", "line": line}
                else:
                    if not line.strip():
                        continue
                    evt = {"type": "log", "line": line}

                try:
                    self._emit(evt)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Browser closed the EventSource — stop the runner ASAP
                    # so Stop actually stops the benchmark, not just the UI.
                    client_gone = True
                    break
                rec_fp.write(json.dumps(evt, ensure_ascii=False) + "\n")
                rec_fp.flush()
                recording.append(evt)
        finally:
            stop_hb.set()
            if client_gone or proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                except Exception:
                    pass

        rc = proc.returncode if proc.poll() is not None else proc.wait()

        with _active_proc_lock:
            if _active_proc is proc:
                _active_proc = None
        complete_evt = {"type": "complete", "mode": "live", "exit_code": rc,
                        "recording_id": rid}
        self._emit(complete_evt)
        rec_fp.write(json.dumps(complete_evt) + "\n")
        rec_fp.close()
        recording.append(complete_evt)

        # Sidecar meta for fast /runs listing.
        try:
            meta = _build_meta(recording)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        except Exception as exc:
            sys.stderr.write(f"meta write failed for {rid}: {exc}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    _load_dotenv()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Dashboard: http://{args.host}:{args.port}/")
    print(f"  v2:      http://{args.host}:{args.port}/v2")
    print(f"  default replay: baseline.jsonl")
    print(f"  live:    open the dashboard, tick 'refresh_bench', click Run")
    print(f"  records: {RUNS_DIR.relative_to(DIR)}")
    print("Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown")


if __name__ == "__main__":
    main()
