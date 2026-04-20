"""Context Recovery Benchmark: measures the cost of AI agent onboarding
through different context sources.

This is a DEMO benchmark for Heisenbug 2026 conference.
Measures: tokens, time, messages, accuracy, cost per approach.

5 approaches × 5 verification questions × 3 runs with median.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

GENERATOR_MODEL = "gpt-oss-120b"
EVALUATOR_MODEL = "zai-glm-4.7"

NUM_RUNS = 5

# When set by server.py the runner emits machine-readable progress lines
# (`[EVENT] {...}`) for the dashboard SSE consumer.
EMIT_EVENTS = os.environ.get("RECOVERY_EMIT_EVENTS") == "1"
_EMIT_T0 = time.time()


def emit_event(payload: dict) -> None:
    """Print a one-line JSON event for the live-mode SSE bridge.

    Adds `ts_ms` — milliseconds since the runner started — so a recorded
    stream can be replayed with the same wall-clock dynamics.
    """
    if not EMIT_EVENTS:
        return
    payload = {**payload, "ts_ms": int((time.time() - _EMIT_T0) * 1000)}
    print("[EVENT] " + json.dumps(payload, ensure_ascii=False), flush=True)


# Per-onboarding progress state so each real tool-call inside an onboarder
# can tick the live dashboard in real time (instead of jumping to max
# at the end). Set via onboard_begin / consumed via onboard_tick.
#
# `wall_t0` is the wall-clock start for the *entire approach* (onboarding +
# Phase 1b retrieval eval + verification). `time_ms` emitted in events is
# always wall-time from wall_t0 — so the live timer reflects real elapsed
# duration, not just the sum of generator-LLM latencies.
_ONBOARD_CTX: dict = {"approach": None, "wall_t0": 0.0, "calls": 0, "tokens": 0}


def onboard_begin(approach: str) -> None:
    _ONBOARD_CTX.update({
        "approach": approach,
        "wall_t0": time.time(),
        "calls": 0,
        "tokens": 0,
    })


def wall_ms() -> int:
    """Milliseconds since the current approach started (wall-clock)."""
    t0 = _ONBOARD_CTX.get("wall_t0") or time.time()
    return int((time.time() - t0) * 1000)


def onboard_tick(added_tokens: int = 0, activity: str | None = None) -> None:
    """Increment tool-call counter and emit a progress event.

    `activity` overrides the default "retrieving (N)" string — used by the
    MCP client to surface per-tool-call status (e.g. "helixir: search_memory")
    so the live dashboard shows what's happening even when a call stalls.
    """
    _ONBOARD_CTX["calls"] += 1
    _ONBOARD_CTX["tokens"] += int(added_tokens)
    if _ONBOARD_CTX["approach"]:
        emit_event({
            "type": "approach_progress",
            "approach": _ONBOARD_CTX["approach"],
            "tokens": int(_ONBOARD_CTX["tokens"]),
            "time_ms": wall_ms(),
            "tool_calls_done": int(_ONBOARD_CTX["calls"]),
            "activity": activity or f"retrieving ({_ONBOARD_CTX['calls']})",
        })


def heartbeat(activity: str) -> None:
    """Emit a progress event without incrementing counters — used while
    waiting on a slow/blocking tool call so the UI timer keeps ticking
    and the user can see what stage we're in.
    """
    if not _ONBOARD_CTX.get("approach"):
        return
    emit_event({
        "type": "approach_progress",
        "approach": _ONBOARD_CTX["approach"],
        "tokens": int(_ONBOARD_CTX["tokens"]),
        "time_ms": wall_ms(),
        "tool_calls_done": int(_ONBOARD_CTX["calls"]),
        "activity": activity,
    })

# Helixir MCP binary
HELIXIR_MCP_BIN = "/Users/nikitarulenko/Documents/PROJ/helixir-rs/helixir/target/release/helixir-mcp"
HELIXIR_ENV = {
    "HELIX_HOST": "localhost",
    "HELIX_PORT": "6970",
    "HELIX_INSTANCE": "bench",
    "HELIX_LLM_PROVIDER": "cerebras",
    "HELIX_LLM_MODEL": "gpt-oss-120b",
    "HELIX_LLM_API_KEY": os.environ.get("CEREBRAS_API_KEY", ""),
    "HELIX_EMBEDDING_PROVIDER": "ollama",
    "HELIX_EMBEDDING_MODEL": "nomic-embed-text",
    "HELIX_EMBEDDING_URL": "http://localhost:11434",
    "HELIX_EMBEDDING_API_KEY": "not-needed",
    "RUST_LOG": "helixir=warn",
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
}

# Mem0 API (local)
MEM0_BASE_URL = "http://localhost:8888"
MEM0_USER_ID = "bench"

# ─── Verification Questions ───────────────────────────────────────────
# Same 5 questions for all approaches (from the design doc)

VERIFICATION_QUESTIONS = [
    {
        "id": "Q1",
        "question": "Какая архитектура проекта Bean & Brew? Перечисли все слои и их роли.",
        "gold": "Clean Architecture with 4 layers: entity (domain models, validation, no DB), "
                "repository (data access, SQLite implementation), usecase (business logic, "
                "delegates to repository), handler (HTTP API, chi router, maps errors to status codes). "
                "Each layer testable independently.",
    },
    {
        "id": "Q2",
        "question": "Если API-запрос POST /orders приходит с пустым customer_id и пустым списком items — "
                    "какую ошибку и какой HTTP-статус вернёт сервер? Опиши всю цепочку проверок: "
                    "на каком слое что проверяется и как ошибка превращается в HTTP-код.",
        "gold": "Order.Validate() in entity layer performs sequential checks in order: "
                "(1) CustomerID != \"\" → ErrEmptyCustomerID, (2) len(Items) > 0 → ErrEmptyOrder, "
                "(3) per-item: Quantity>0 → ErrInvalidQuantity, ProductID>0 → ErrInvalidProduct. "
                "The FIRST failing check determines the error (priority order) — so empty customer_id "
                "returns ErrEmptyCustomerID without checking items. OrderUseCase.Create propagates "
                "the error up. API handler calls writeError() in handler/helpers.go which maps "
                "ErrEmptyCustomerID → HTTP 400 (Bad Request). Chain: entity validation → usecase "
                "propagation → handler status mapping.",
    },
    {
        "id": "Q3",
        "question": "Почему TestIntegrationProductSearch назвали flaky и не удалили? Какой альтернативный "
                    "фикс рассматривался и почему его отвергли? Объясни trade-off.",
        "gold": "Flaky because TestIntegrationProductSearch uses LIKE queries with Cyrillic text in SQLite; "
                "behavior of case-insensitive LIKE for Unicode varies across SQLite versions and depends "
                "on insert order. Not deleted because it's the only test covering Cyrillic search paths. "
                "The alternative fix discussed was adding the ICU extension to SQLite — this would enable "
                "correct Unicode LIKE. Rejected because: ICU adds +5MB to binary size, requires "
                "CGO_ENABLED=1 (breaking simple cross-compilation), and significantly complicates CI "
                "pipeline. Trade-off: accepted documented flakiness instead of ICU, since test cost "
                "(occasional retry) is lower than ICU integration cost.",
    },
    {
        "id": "Q4",
        "question": "Сколько всего test runs в проекте и как они распределены по 4 слоям? "
                    "Назови точное число на каждом слое и общую сумму.",
        "gold": "Total: 637 test runs. Breakdown by layer: Entity = 237 runs (pure unit tests, "
                "no DB — validation, discount, state transitions, summary). Repository = 94 runs "
                "(integration tests via setupTestDB — CRUD, pagination, search). Usecase = 127 runs "
                "(via setupUC — business logic, lifecycle, pagination). API handler = 179 runs "
                "(via setupTestServer — REST endpoints, error codes, full cycles). "
                "Sum: 237 + 94 + 127 + 179 = 637.",
    },
    {
        "id": "Q5",
        "question": "Если разработчик меняет схему миграций в migrations.go — какие тесты продолжат "
                    "работать БЕЗ модификаций? Назови конкретный слой, точное число тестов и объясни почему "
                    "именно они не пострадают.",
        "gold": "Only Entity layer tests (237 runs) will continue working unchanged. Reason: entity tests "
                "are pure unit tests that exercise struct methods (Validate, ApplyDiscount, CalculateTotal, "
                "CanCancel/CanComplete) without any database — they don't call setupTestDB, setupTestServer, "
                "or setupUC, so they never touch migrations. All OTHER layers depend on migrations: "
                "Repository (94) uses setupTestDB which runs RunMigrations; Usecase (127) uses setupUC "
                "which creates a DB with migrations; API (179) uses setupTestServer which also runs "
                "RunMigrations. So 400 tests (94 + 127 + 179) out of 637 break; only 237 entity tests "
                "survive unchanged.",
    },
    {
        "id": "Q6",
        "question": "Ревьюер предлагает: 'перенесём Product.ApplyDiscount из entity-слоя в usecase-слой "
                    "для консистентности с другими бизнес-операциями'. Это хорошая идея с точки зрения "
                    "архитектуры проекта? Обоснуй через конкретные свойства кода и тестов.",
        "gold": "Bad idea. ApplyDiscount is pure business logic on a single entity — it has no cross-entity "
                "orchestration, no repository calls, no I/O. Per Clean Architecture, such pure behaviour "
                "belongs in the entity layer (innermost, no outward dependencies). Evidence: ApplyDiscount "
                "is already thoroughly tested at entity layer (TestUnitProductApplyDiscount and variants "
                "— dozens of subtests for boundary percents, zero/large prices, consistency). The usecase "
                "layer in this project is for orchestration — e.g., OrderUseCase.Create coordinates "
                "Product lookup + Order creation + CalculateTotal. Moving ApplyDiscount to usecase would: "
                "(1) duplicate existing entity tests, (2) add an unnecessary delegation layer, (3) couple "
                "a pure math operation to application state, violating the dependency rule. The whole "
                "point of entity isolation is that 237 entity tests run in milliseconds with no DB setup. "
                "Same reasoning applies to CalculateTotal, Validate, CanCancel/CanComplete — all pure "
                "entity methods.",
    },
]

# Evaluation prompt for verification answers
EVAL_PROMPT_RECOVERY = """You are an expert evaluator. Score the ANSWER against the GOLD STANDARD on 5 criteria (1-4 scale):

1 = Incorrect/Missing, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct

Criteria:
1. **Accuracy** (1-4): Are the facts correct?
2. **Completeness** (1-4): Are ALL key points from gold standard covered?
3. **Context Utilization** (1-4): Does the answer use real project details, not generic advice?
4. **Specificity** (1-4): Are concrete numbers, names, and details provided?
5. **Causal Depth** (1-4): Does the answer explain WHY — cause chains, mechanism, trade-offs — not just WHAT?
   - 1 = only facts, no causal explanation
   - 2 = one "because" / "so that" link
   - 3 = 2–3 connected causes OR an explicit trade-off articulated
   - 4 = multi-step chain (A → because B → therefore C) AND a counter-factual / trade-off

GOLD STANDARD:
{gold}

ANSWER:
{answer}

Return ONLY a JSON block:
```json
{{"accuracy": X, "completeness": X, "context_utilization": X, "specificity": X, "causal_depth": X, "total": X}}
```"""


# Evaluation prompt for the RAW retrieval context (before generator synthesises
# an answer). Measures what the memory system actually returned — so a flat
# bag-of-facts vs a graph of typed edges gets scored differently even if the
# downstream LLM can confabulate a plausible answer from either.
EVAL_PROMPT_RETRIEVAL = """You evaluate the QUALITY of a RETRIEVED CONTEXT (not an answer). Score the CONTEXT on 3 criteria (1-4 scale):

1 = Very weak, 2 = Partial, 3 = Good, 4 = Excellent

Criteria:
1. **Fact Coverage** (1-4): Does the context contain the facts that the REFERENCE QUESTIONS would need?
2. **Causal Density** (1-4): Are cause-effect links EXPLICITLY present in the context, not just atomic facts?
   - 1 = only atomic facts ("X is Y"), no links
   - 2 = a few "because" / "потому что" / "reason:" markers
   - 3 = multiple explicit links (BECAUSE/IMPLIES/CONTRADICTS/trade-off/therefore) across topics
   - 4 = structured reasoning chains (A → B → C) with typed edges or explicit because-therefore structure visible
3. **Structure** (1-4): Is the context organised (sections, typed relations, named entities) vs a flat bag of strings?

REFERENCE QUESTIONS (the context will be used to answer these):
{questions}

CONTEXT (what the retrieval system returned):
{context}

Return ONLY a JSON block:
```json
{{"fact_coverage": X, "causal_density": X, "structure": X, "total": X}}
```"""

# ─── HTTP Client ──────────────────────────────────────────────────────

_http = httpx.Client(
    timeout=httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0),
    transport=httpx.HTTPTransport(retries=2),
)


def call_llm(messages, model=GENERATOR_MODEL, temperature=0.2, max_tokens=2000):
    """Call Cerebras LLM. Returns (content, usage_dict, latency_ms)."""
    t0 = time.time()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if model == EVALUATOR_MODEL:
        payload["max_completion_tokens"] = max_tokens
        del payload["max_tokens"]

    resp = _http.post(
        f"{CEREBRAS_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    latency = int((time.time() - t0) * 1000)
    data = resp.json()
    msg = data["choices"][0]["message"]
    # Reasoning models (zai-glm-4.7) sometimes burn the whole completion
    # budget on hidden reasoning and return content="". Fall back to the
    # reasoning_content field — judges often emit the JSON inline there.
    content = (msg.get("content") or "").strip()
    if not content:
        rc = (msg.get("reasoning_content") or "").strip()
        if rc:
            content = rc
    usage = data.get("usage", {})
    if not content:
        finish = data["choices"][0].get("finish_reason", "?")
        sys.stderr.write(
            f"[call_llm] {model} returned EMPTY content "
            f"(finish={finish}, usage={usage})\n"
        )
    return content, usage, latency


def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for mixed Cyrillic/English."""
    return max(1, len(text) // 4)


ANSWER_KEYS = ["accuracy", "completeness", "context_utilization", "specificity", "causal_depth"]
RETRIEVAL_KEYS = ["fact_coverage", "causal_density", "structure"]


def extract_scores(text, keys=None):
    """Extract JSON scores from evaluator response.

    `keys` selects the scoring schema:
      - ANSWER_KEYS (default) for EVAL_PROMPT_RECOVERY  → 5 criteria, max 20
      - RETRIEVAL_KEYS for EVAL_PROMPT_RETRIEVAL        → 3 criteria, max 12
    """
    import re
    if keys is None:
        keys = ANSWER_KEYS
    raw = text.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if "{" in part:
                raw = part
                break

    try:
        scores = json.loads(raw)
        if isinstance(scores, dict) and any(k in scores for k in keys):
            scores["total"] = sum(scores.get(k, 0) for k in keys)
            return scores
    except (json.JSONDecodeError, TypeError):
        pass

    for match in re.finditer(r'\{[^{}]+\}', text):
        try:
            c = json.loads(match.group())
            if isinstance(c, dict) and any(k in c for k in keys):
                c["total"] = sum(c.get(k, 0) for k in keys)
                return c
        except (json.JSONDecodeError, TypeError):
            continue

    # Last-resort regex sweep: pick up "fact_coverage: 3" / "accuracy = 4" /
    # "**Completeness**: 2" style outputs when the eval didn't return JSON.
    # Better than silently falling back to all zeros — we saw this on live
    # runs where the evaluator drifted to prose explanations.
    scores = {}
    for k in keys:
        m = re.search(rf'["*]?{k}["*]?\s*[:=]\s*(\d+)', text, re.IGNORECASE)
        if m:
            try:
                scores[k] = int(m.group(1))
            except ValueError:
                pass
    if scores:
        scores["total"] = sum(scores.get(k, 0) for k in keys)
        for k in keys:
            scores.setdefault(k, 0)
        return scores

    sys.stderr.write(
        f"[extract_scores] could not parse scores for keys={keys}; "
        f"response head={text[:200]!r}\n"
    )
    return {k: 0 for k in keys + ["total"]}


# ─── MCP Clients ──────────────────────────────────────────────────────

class HelixirMCPClient:
    """JSON-RPC over stdio to helixir-mcp binary."""

    def __init__(self):
        self.proc = None
        self._msg_id = 0

    def start(self):
        self.proc = subprocess.Popen(
            [HELIXIR_MCP_BIN],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=HELIXIR_ENV,
        )
        resp = self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bench-recovery", "version": "1.0"},
        })
        self._notify("notifications/initialized", {})
        return resp

    def stop(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    # Hard cap on a single MCP tool response — if the backing Helixir daemon
    # stalls (e.g. localhost:6970 not responding) we don't want `readline()`
    # to block the whole benchmark. Per-call timeout lets us skip + log.
    RPC_TIMEOUT_S = 20.0

    def _rpc(self, method, params, timeout=None):
        self._msg_id += 1
        msg = json.dumps({"jsonrpc": "2.0", "id": self._msg_id, "method": method, "params": params}) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()

        deadline = time.time() + (timeout if timeout is not None else self.RPC_TIMEOUT_S)
        # select() on the stdout fd with a short budget, then blocking readline
        # if the fd is ready — keeps the event loop responsive and lets the
        # caller emit heartbeats while waiting.
        fd = self.proc.stdout.fileno()
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                sys.stderr.write(f"[helixir-mcp] RPC {method} timed out after "
                                 f"{timeout or self.RPC_TIMEOUT_S:.0f}s — skipping\n")
                return None
            r, _, _ = select.select([fd], [], [], min(remaining, 1.0))
            if r:
                line = self.proc.stdout.readline().decode().strip()
                try:
                    return json.loads(line) if line else None
                except json.JSONDecodeError as exc:
                    sys.stderr.write(f"[helixir-mcp] bad RPC response: {exc}; line={line!r}\n")
                    return None
            # fd not ready — loop to re-check deadline (caller can emit heartbeats
            # in the gaps by wrapping call_tool, see below)

    def _notify(self, method, params):
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()

    def call_tool(self, name, args, timeout=None):
        resp = self._rpc("tools/call", {"name": name, "arguments": args}, timeout=timeout)
        if resp and "result" in resp:
            return "\n".join(
                item["text"] for item in resp["result"].get("content", [])
                if item.get("type") == "text"
            )
        return ""

    def search_memory(self, query, limit=15):
        return self.call_tool("search_memory", {"query": query, "user_id": "bench", "mode": "full", "limit": limit})

    def search_reasoning_chain(self, query, mode="causal"):
        return self.call_tool("search_reasoning_chain", {"query": query, "user_id": "bench", "chain_mode": mode, "max_depth": 3})

    def search_by_concept(self, query, concept_type="fact"):
        return self.call_tool("search_by_concept", {"query": query, "user_id": "bench", "concept_type": concept_type, "limit": 10})


class Mem0Client:
    """HTTP client for local Mem0 API."""

    def search(self, query, limit=20):
        try:
            resp = _http.post(
                f"{MEM0_BASE_URL}/search",
                json={"query": query, "user_id": MEM0_USER_ID, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list):
                return "\n\n".join(
                    r.get("memory", r.get("text", str(r))) for r in results
                )
            return str(results)
        except Exception as e:
            return f"[Mem0 error: {e}]"

    def list_all(self, limit=100):
        try:
            resp = _http.get(f"{MEM0_BASE_URL}/memories", params={"user_id": MEM0_USER_ID, "limit": limit})
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(results, list):
                return "\n\n".join(
                    r.get("memory", r.get("text", str(r))) for r in results
                )
            return str(results)
        except Exception as e:
            return f"[Mem0 error: {e}]"


# ─── Onboarding Strategies ───────────────────────────────────────────

def onboard_md_files(context_file):
    """Read flat MD context. Returns (context_text, metrics)."""
    t0 = time.time()
    with open(context_file) as f:
        episodes = json.load(f)
    context = "\n\n".join(f"### {ep['name']}\n{ep['content']}" for ep in episodes)
    elapsed = int((time.time() - t0) * 1000)
    onboard_tick(added_tokens=estimate_tokens(context))
    return context, {
        "tool_calls": 1,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


def onboard_github_issues(context_file):
    """Simulate GitHub Issues: same content but structured as issues."""
    t0 = time.time()
    with open(context_file) as f:
        episodes = json.load(f)
    # Format as issue-like structure
    parts = []
    for i, ep in enumerate(episodes, 1):
        parts.append(f"## Issue #{i}: {ep['name']}\n**Body:**\n{ep['content']}")
    context = "\n\n---\n\n".join(parts)
    elapsed = int((time.time() - t0) * 1000)
    onboard_tick(added_tokens=estimate_tokens(context))
    return context, {
        "tool_calls": 1,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


def onboard_mem0():
    """Retrieve context from Mem0 via semantic search."""
    client = Mem0Client()
    t0 = time.time()

    # Topic-neutral onboarding queries covering 5 project areas. Not tuned
    # to a specific verification question — simulates a new engineer asking
    # broad "tell me about X" questions.
    queries = [
        "Bean & Brew project architecture and layers",
        "Order domain validation errors and HTTP status mapping",
        "known issues flaky tests and trade-offs",
        "test coverage counts per layer entity repository usecase API",
        "test infrastructure setup helpers migrations dependencies",
    ]

    parts = []
    total_calls = 0
    for q in queries:
        result = client.search(q, limit=10)
        if result and not result.startswith("[Mem0 error"):
            parts.append(f"### Search: {q}\n{result}")
            total_calls += 1
            onboard_tick(added_tokens=estimate_tokens(result))

    # Also list all memories for completeness
    all_mem = client.list_all(limit=50)
    if all_mem and not all_mem.startswith("[Mem0 error"):
        parts.append(f"### All Memories\n{all_mem}")
        total_calls += 1
        onboard_tick(added_tokens=estimate_tokens(all_mem))

    context = "\n\n".join(parts)
    elapsed = int((time.time() - t0) * 1000)
    return context, {
        "tool_calls": total_calls,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


def onboard_helixir_mcp():
    """Retrieve context from Helixir MCP using all 3 tools."""
    client = HelixirMCPClient()
    client.start()
    t0 = time.time()

    # Topic-neutral onboarding queries covering 5 project areas. Not tuned
    # to a specific verification question.
    queries = [
        ("Bean & Brew Clean Architecture 4 layers", "forward", "fact"),
        ("Order validation errors HTTP status mapping chain", "causal", "fact"),
        ("known issues flaky tests ICU trade-off SQLite", "causal", "opinion"),
        ("test coverage counts per layer entity repository usecase API", "forward", "fact"),
        ("test infrastructure setupTestDB setupUC migrations dependencies", "causal", "fact"),
    ]

    parts = []
    total_calls = 0

    for q_idx, (query, chain_mode, concept_type) in enumerate(queries, 1):
        # search_memory
        heartbeat(f"helixir Q{q_idx}/5: search_memory")
        result = client.search_memory(query, limit=10)
        if result:
            parts.append(f"### Memory: {query}\n{result}")
            total_calls += 1
            onboard_tick(added_tokens=estimate_tokens(result),
                         activity=f"helixir Q{q_idx}/5: memory ({total_calls} calls)")

        # search_reasoning_chain
        heartbeat(f"helixir Q{q_idx}/5: search_reasoning_chain")
        chain = client.search_reasoning_chain(query, mode=chain_mode)
        if chain:
            parts.append(f"### Reasoning Chain ({chain_mode}): {query}\n{chain}")
            total_calls += 1
            onboard_tick(added_tokens=estimate_tokens(chain),
                         activity=f"helixir Q{q_idx}/5: chain ({total_calls} calls)")

        # search_by_concept
        heartbeat(f"helixir Q{q_idx}/5: search_by_concept")
        concept = client.search_by_concept(query, concept_type=concept_type)
        if concept:
            parts.append(f"### Concept ({concept_type}): {query}\n{concept}")
            total_calls += 1
            onboard_tick(added_tokens=estimate_tokens(concept),
                         activity=f"helixir Q{q_idx}/5: concept ({total_calls} calls)")

    context = "\n\n".join(parts)
    elapsed = int((time.time() - t0) * 1000)

    client.stop()
    return context, {
        "tool_calls": total_calls,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


APPROACHES = {
    "md_files": onboard_md_files,
    "github_issues": onboard_github_issues,
    "mem0": onboard_mem0,
    "helixir_mcp": onboard_helixir_mcp,
}


# ─── Verification Phase ──────────────────────────────────────────────

def run_verification(context_text, run_id, approach=None, onboard=None,
                     scale=1.0, running=None):
    """Ask 5 questions with retrieved context, evaluate answers.

    `approach` / `onboard` / `scale` / `running` are only used for live-mode
    SSE events. Progress counters grow **monotonically** across all runs:
    each question's token/time delta is multiplied by `scale` (typically
    `1/num_runs`) and added to the shared `running` carrier, so after
    num_runs × len(VERIFICATION_QUESTIONS) ticks the total lands near the
    median-run aggregate — no saw-tooth between runs, no overshoot.
    """
    system_msg = (
        "You are an AI assistant. You have just recovered the context of the Bean & Brew "
        "Go coffee shop project from the following source:\n\n"
        f"{context_text}\n\n"
        "Answer the questions based ONLY on this context. Be specific with numbers, "
        "test names, file paths, and technical details."
    )

    results = []
    total_input_tokens = estimate_tokens(system_msg)
    total_output_tokens = 0
    total_time = 0

    onboard = onboard or {"tokens": 0, "time_ms": 0, "tool_calls": 0}
    if running is None:
        running = {"tokens": 0.0, "time_ms": 0.0, "tool_time_ms": 0.0}
    # Older callers may pass a dict without tool_time_ms — initialise lazily.
    running.setdefault("tool_time_ms", 0.0)

    for q in VERIFICATION_QUESTIONS:
        print(f"    R{run_id} [{q['id']}]...", end="", flush=True)

        answer, usage, latency = call_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": q["question"]},
        ])

        # Token accounting
        inp_tok = usage.get("prompt_tokens", estimate_tokens(system_msg + q["question"]))
        out_tok = usage.get("completion_tokens", estimate_tokens(answer))
        total_input_tokens += inp_tok
        total_output_tokens += out_tok
        total_time += latency

        # Evaluate
        eval_text, _, _ = call_llm(
            [{"role": "user", "content": EVAL_PROMPT_RECOVERY.format(gold=q["gold"], answer=answer)}],
            model=EVALUATOR_MODEL, temperature=0.0, max_tokens=8000,
        )
        scores = extract_scores(eval_text)
        total = scores.get("total", 0)

        results.append({
            "question_id": q["id"],
            "question": q["question"],
            "answer": answer[:500],
            "scores": scores,
            "total": total,
            "latency_ms": latency,
            "input_tokens": inp_tok,
            "output_tokens": out_tok,
        })
        print(f" {total}/20 ({latency}ms)")

        if approach:
            # Accumulate scaled deltas into the shared carrier so the
            # counter grows monotonically across all num_runs × 5 questions
            # and lands near the median-run aggregate at the end.
            running["tokens"] += (inp_tok + out_tok) * scale
            running["time_ms"] += latency * scale
            # Tool time accrues each generator latency (scaled). Evaluator
            # latency is small + not tracked here — keeps tool_time_ms a
            # clean "time spent waiting on the answer-generating LLM".
            running["tool_time_ms"] += latency * scale
            emit_event({
                "type": "approach_progress",
                "approach": approach,
                "tokens": int(onboard["tokens"] + running["tokens"]),
                # time_ms = real wall-clock from approach_start (includes
                # Phase 1b retrieval eval + evaluator calls + all overhead),
                # NOT just generator latency. Matches what a user sees.
                "time_ms": wall_ms(),
                "tool_time_ms": int(onboard.get("time_ms", 0) + running["tool_time_ms"]),
                "tool_calls_done": int(onboard["tool_calls"]),
                "activity": f"R{run_id} {q['id']} → {total}/20",
            })

    return results, {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_time_ms": total_time,
        "messages": len(VERIFICATION_QUESTIONS),
    }


# ─── Main Runner ─────────────────────────────────────────────────────

@dataclass
class ApproachResult:
    approach: str
    onboarding_metrics: dict = field(default_factory=dict)
    verification_runs: list = field(default_factory=list)
    verification_stats: dict = field(default_factory=dict)
    aggregate: dict = field(default_factory=dict)


def run_approach(approach, context_file, num_runs=NUM_RUNS):
    """Run full benchmark for one approach."""
    print(f"\n{'='*60}")
    print(f"Approach: {approach}")
    print(f"{'='*60}")
    emit_event({"type": "approach_start", "approach": approach})

    # Phase 1: Onboarding
    print(f"\n  Phase 1: Onboarding...")
    onboard_fn = APPROACHES[approach]
    onboard_begin(approach)  # enables incremental onboard_tick() emits
    if approach in ("md_files", "github_issues"):
        context, onboard_metrics = onboard_fn(context_file)
    else:
        context, onboard_metrics = onboard_fn()

    print(f"    Context: {onboard_metrics['context_chars']:,} chars "
          f"(~{onboard_metrics['context_tokens_est']:,} tokens)")
    print(f"    Tool calls: {onboard_metrics['tool_calls']}")
    print(f"    Retrieval time: {onboard_metrics['retrieval_time_ms']}ms")
    emit_event({
        "type": "approach_progress",
        "approach": approach,
        "tokens": int(onboard_metrics["context_tokens_est"]),
        "time_ms": wall_ms(),
        "tool_calls_done": int(onboard_metrics["tool_calls"]),
        "activity": "retrieval eval…",
    })

    # Phase 1b: Retrieval-quality evaluation (the C in plan C+A).
    # Scores the RAW retrieved context BEFORE the generator writes an answer —
    # so a flat bag-of-facts vs a graph with BECAUSE/IMPLIES edges is
    # distinguishable even when downstream LLM can confabulate plausible prose
    # from either. Gives us: fact_coverage / causal_density / structure.
    print(f"  Phase 1b: Retrieval-quality evaluation...")
    questions_block = "\n".join(
        f"- {q['id']}: {q['question']}" for q in VERIFICATION_QUESTIONS
    )
    # Truncate context for the judge to avoid overflowing eval model. zai-glm-4.7
    # is a reasoning model whose hidden reasoning eats max_completion_tokens —
    # smaller prompt + larger budget leaves room for both reasoning AND visible
    # JSON output. 10k char cap + 8k completion budget is what consistently
    # produces non-empty content in practice.
    judge_context = context if len(context) <= 10000 else context[:10000] + "\n\n[...truncated for retrieval eval...]"
    retr_eval_text, _, _ = call_llm(
        [{"role": "user", "content": EVAL_PROMPT_RETRIEVAL.format(
            questions=questions_block, context=judge_context
        )}],
        model=EVALUATOR_MODEL, temperature=0.0, max_tokens=8000,
    )
    retrieval_scores = extract_scores(retr_eval_text, keys=RETRIEVAL_KEYS)
    retrieval_total = retrieval_scores.get("total", 0)
    print(f"    Retrieval scores: {retrieval_scores} (max 12)")

    # Push retrieval scores to the live dashboard immediately — without this
    # the card's Retrieval % stays at 0 until approach_complete (after 5
    # verification runs), even though the evaluator already produced a score.
    emit_event({
        "type": "approach_progress",
        "approach": approach,
        "tokens": int(onboard_metrics["context_tokens_est"]),
        "time_ms": wall_ms(),
        # Tool time at this point = retrieval (onboarding) only; evaluator
        # time is wall-only, intentionally not added to tool_time_ms.
        "tool_time_ms": int(onboard_metrics["retrieval_time_ms"]),
        "tool_calls_done": int(onboard_metrics["tool_calls"]),
        "activity": f"retrieval eval → {retrieval_total}/12",
        "retrieval_quality_pct": round(retrieval_total / 12 * 100, 1),
        "retrieval_scores": retrieval_scores,
    })

    # Phase 2: Verification (multiple runs)
    all_runs = []
    onboard_tokens = onboard_metrics["context_tokens_est"]
    onboard_time = onboard_metrics["retrieval_time_ms"]
    # Shared carrier: scaled tokens/time accumulate across all runs, so the
    # live counter is monotonic (no saw-tooth between R1→R2→R3) and ends
    # near the median-run aggregate shown on `approach_complete`.
    running_progress = {"tokens": 0.0, "time_ms": 0.0}
    progress_scale = 1.0 / max(num_runs, 1)
    for run_id in range(1, num_runs + 1):
        print(f"\n  Phase 2: Verification run {run_id}/{num_runs}")
        results, run_metrics = run_verification(
            context, run_id,
            approach=approach,
            onboard={
                "tokens": onboard_tokens,
                "time_ms": onboard_time,
                "tool_calls": onboard_metrics["tool_calls"],
            },
            scale=progress_scale,
            running=running_progress,
        )
        run_total = sum(r["total"] for r in results)
        all_runs.append({
            "run_id": run_id,
            "results": results,
            "metrics": run_metrics,
            "total_score": run_total,
        })
        print(f"    Run {run_id} total: {run_total}/{len(VERIFICATION_QUESTIONS) * 20}")

    # Statistics
    totals = [r["total_score"] for r in all_runs]
    per_q_scores = {}
    for q in VERIFICATION_QUESTIONS:
        qscores = []
        for run in all_runs:
            for r in run["results"]:
                if r["question_id"] == q["id"]:
                    qscores.append(r["total"])
        per_q_scores[q["id"]] = {
            "median": statistics.median(qscores),
            "mean": round(statistics.mean(qscores), 2),
            "scores": qscores,
        }

    stats = {
        "total_median": statistics.median(totals),
        "total_mean": round(statistics.mean(totals), 2),
        "total_stddev": round(statistics.stdev(totals), 2) if len(totals) > 1 else 0,
        "per_question": per_q_scores,
    }

    # Aggregate metrics (median run)
    median_run = all_runs[totals.index(statistics.median(totals))] if len(totals) % 2 == 1 else all_runs[0]
    rm = median_run["metrics"]

    # Cost estimation (Cerebras pricing approximation: $0.60/M input, $0.60/M output)
    total_input = onboard_metrics["context_tokens_est"] + rm["total_input_tokens"]
    total_output = rm["total_output_tokens"]
    cost_estimate = (total_input * 0.6 + total_output * 0.6) / 1_000_000

    # Part A/B/C breakdown — matches v3 methodology:
    #   A = Facts (retrieval of concrete numbers / structure, including
    #       multi-source facts that only require composition without reasoning)
    #   B = Reasoning (trade-off analysis, design judgment — requires
    #       weighing evidence, not just retrieving it)
    #   C = Decisions (consequence analysis, impact of change)
    part_groups = {
        "Q1": "a", "Q2": "a", "Q4": "a",   # architecture; validation chain; test counts → Facts
        "Q3": "b", "Q6": "b",              # flaky trade-off; ApplyDiscount placement → Reasoning
        "Q5": "c",                         # migration impact analysis                → Decisions
    }
    part_scores = {"a": [], "b": [], "c": []}
    for q in VERIFICATION_QUESTIONS:
        part = part_groups.get(q["id"])
        if part is not None:
            part_scores[part].append(per_q_scores[q["id"]]["median"])

    def _part_pct(scores):
        if not scores:
            return 0.0
        return round(sum(scores) / (len(scores) * 20) * 100, 1)

    # total_time_ms = REAL wall-clock for the entire approach (onboarding +
    # retrieval eval + all verification runs + evaluator calls). The previous
    # sum-of-latencies value is kept as `tool_time_ms` for detailed analysis,
    # since it measures LLM-compute cost vs the user-facing end-to-end time.
    wall_total_ms = wall_ms()
    tool_time_ms = onboard_metrics["retrieval_time_ms"] + rm["total_time_ms"]
    aggregate = {
        "context_tokens": onboard_metrics["context_tokens_est"],
        "verification_input_tokens": rm["total_input_tokens"],
        "verification_output_tokens": rm["total_output_tokens"],
        "total_tokens": total_input + total_output,
        "retrieval_time_ms": onboard_metrics["retrieval_time_ms"],
        "verification_time_ms": rm["total_time_ms"],
        "total_time_ms": wall_total_ms,
        "tool_time_ms": tool_time_ms,
        "tool_calls": onboard_metrics["tool_calls"],
        "messages": rm["messages"],
        "accuracy_pct": round(stats["total_median"] / (len(VERIFICATION_QUESTIONS) * 20) * 100, 1),
        "part_a_pct": _part_pct(part_scores["a"]),
        "part_b_pct": _part_pct(part_scores["b"]),
        "part_c_pct": _part_pct(part_scores["c"]),
        "retrieval_quality_pct": round(retrieval_total / 12 * 100, 1),
        "retrieval_scores": retrieval_scores,
        "cost_estimate_usd": round(cost_estimate, 6),
        "cost_performance_ratio": round(stats["total_median"] / max(cost_estimate, 0.000001), 1),
    }

    print(f"\n  Summary: {approach}")
    print(f"    Accuracy: {aggregate['accuracy_pct']}%")
    print(f"    Retrieval quality: {aggregate['retrieval_quality_pct']}% "
          f"(fact={retrieval_scores.get('fact_coverage',0)}/4, "
          f"causal={retrieval_scores.get('causal_density',0)}/4, "
          f"struct={retrieval_scores.get('structure',0)}/4)")
    print(f"    Total tokens: {aggregate['total_tokens']:,}")
    print(f"    Total time: {aggregate['total_time_ms']}ms")
    print(f"    Cost: ${aggregate['cost_estimate_usd']:.6f}")
    print(f"    Cost/Perf: {aggregate['cost_performance_ratio']}")
    emit_event({
        "type": "approach_complete",
        "approach": approach,
        "metrics": aggregate,
    })

    return ApproachResult(
        approach=approach,
        onboarding_metrics=onboard_metrics,
        verification_runs=all_runs,
        verification_stats=stats,
        aggregate=aggregate,
    )


def save_results(results, output_dir="."):
    """Save all results to JSON files."""
    # Per-approach files
    for r in results:
        path = Path(output_dir) / f"recovery_{r.approach}.json"
        with open(path, "w") as f:
            json.dump(asdict(r), f, indent=2, ensure_ascii=False)
        print(f"  Saved: {path}")

    # Comparison summary
    summary = {
        "benchmark": "context_recovery",
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "generator_model": GENERATOR_MODEL,
        "evaluator_model": EVALUATOR_MODEL,
        "num_runs": NUM_RUNS,
        "num_questions": len(VERIFICATION_QUESTIONS),
        "max_score": len(VERIFICATION_QUESTIONS) * 20,
        "max_retrieval_score": 12,
        "approaches": {},
    }

    for r in results:
        summary["approaches"][r.approach] = r.aggregate

    path = Path(output_dir) / "recovery_comparison.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")

    # Print comparison table
    print(f"\n{'='*96}")
    print(f"{'Approach':<18} {'Tokens':>8} {'Time(ms)':>10} {'Accuracy':>10} {'Retrieval':>10} {'Cost($)':>10} {'C/P':>6}")
    print(f"{'-'*96}")
    for r in results:
        a = r.aggregate
        print(f"{r.approach:<18} {a['total_tokens']:>8,} {a['total_time_ms']:>10,} "
              f"{a['accuracy_pct']:>9.1f}% {a.get('retrieval_quality_pct', 0):>9.1f}% "
              f"${a['cost_estimate_usd']:>9.6f} {a['cost_performance_ratio']:>6.1f}")
    print(f"{'='*96}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python benchmark_context_recovery.py <approach|all> [context_file] [num_runs]")
        print(f"Approaches: {', '.join(APPROACHES.keys())}, all")
        sys.exit(1)

    approach = sys.argv[1]
    context_file = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parent.parent / "shared" / "data" / "test_context.json")
    num_runs = int(sys.argv[3]) if len(sys.argv) > 3 else NUM_RUNS

    if approach == "all":
        approaches = list(APPROACHES.keys())
    else:
        approaches = [approach]

    results = []
    for a in approaches:
        result = run_approach(a, context_file, num_runs)
        results.append(result)

    output_dir = str(Path(__file__).resolve().parent.parent / "results")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    save_results(results, output_dir)


if __name__ == "__main__":
    main()
