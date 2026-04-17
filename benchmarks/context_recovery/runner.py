"""Context Recovery Benchmark: measures the cost of AI agent onboarding
through different context sources.

This is a DEMO benchmark for Heisenbug 2026 conference.
Measures: tokens, time, messages, accuracy, cost per approach.

5 approaches × 5 verification questions × 3 runs with median.
"""
from __future__ import annotations

import json
import os
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

NUM_RUNS = 3

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
        "question": "Почему в проекте выбрали SQLite, а не PostgreSQL? Какие недостатки приняли?",
        "gold": "SQLite chosen for: single binary (no DB server), in-memory tests (<1ms setup, "
                "no Docker/testcontainers), small project scope (coffee shop, single user). "
                "PostgreSQL rejected: needs Docker for tests, complex CI, overkill. "
                "Accepted downsides: broken LIKE with Unicode (causes flaky test), "
                "no concurrent writes, DB size limit.",
    },
    {
        "id": "Q3",
        "question": "Какой тест в проекте является flaky и почему? Почему его не удалили?",
        "gold": "TestIntegrationProductSearch is flaky due to LIKE query with Cyrillic text "
                "in SQLite. Fixing requires ICU extension (+5MB binary, CGO_ENABLED=1, complex CI). "
                "Cost exceeds benefit — test passes 9/10. Not deleted because it's the only test "
                "for Cyrillic search. Trade-off: documented flakiness instead of ICU fix.",
    },
    {
        "id": "Q4",
        "question": "Сколько всего тестов в проекте и как они распределены по слоям?",
        "gold": "637 test runs across 4 layers. Entity layer: 237 runs — validation, "
                "business logic, discount calculations, state transitions, UTF-8 summary. "
                "Repository layer: 94 runs — CRUD, pagination, search, timestamps, bulk ops. "
                "Usecase layer: 127 runs — business validation, status transitions, lifecycle, "
                "pagination edge cases. API handler layer: 179 runs — REST endpoints, "
                "error codes, validation cases, CRUD full cycles.",
    },
    {
        "id": "Q5",
        "question": "Что сломается если изменить схему миграций (migrations.go)?",
        "gold": "~400 out of 637 test runs depend on migrations via setupTestDB/setupTestServer/setupUC. "
                "Only 237 entity unit tests are independent (no DB). Breakdown: 94 integration tests "
                "(via setupTestDB), 179 API tests (via setupTestServer which calls RunMigrations), "
                "127 usecase tests (via setupUC which creates DB). ~63% of all tests will break.",
    },
]

# Evaluation prompt for verification answers
EVAL_PROMPT_RECOVERY = """You are an expert evaluator. Score the ANSWER against the GOLD STANDARD on 4 criteria (1-4 scale):

1 = Incorrect/Missing, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct

Criteria:
1. **Accuracy** (1-4): Are the facts correct?
2. **Completeness** (1-4): Are ALL key points from gold standard covered?
3. **Context Utilization** (1-4): Does the answer use real project details, not generic advice?
4. **Specificity** (1-4): Are concrete numbers, names, and details provided?

GOLD STANDARD:
{gold}

ANSWER:
{answer}

Return ONLY a JSON block:
```json
{{"accuracy": X, "completeness": X, "context_utilization": X, "specificity": X, "total": X}}
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
    content = data["choices"][0]["message"].get("content", "") or ""
    usage = data.get("usage", {})
    return content, usage, latency


def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for mixed Cyrillic/English."""
    return max(1, len(text) // 4)


def extract_scores(text):
    """Extract JSON scores from evaluator response."""
    import re
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

    keys = ["accuracy", "completeness", "context_utilization", "specificity"]
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

    def _rpc(self, method, params):
        self._msg_id += 1
        msg = json.dumps({"jsonrpc": "2.0", "id": self._msg_id, "method": method, "params": params}) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()
        line = self.proc.stdout.readline().decode().strip()
        return json.loads(line) if line else None

    def _notify(self, method, params):
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n"
        self.proc.stdin.write(msg.encode())
        self.proc.stdin.flush()

    def call_tool(self, name, args):
        resp = self._rpc("tools/call", {"name": name, "arguments": args})
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

    queries = [
        "Bean & Brew project architecture layers",
        "SQLite database choice testing",
        "flaky test TestIntegrationProductSearch",
        "test coverage distribution layers entity repository usecase handler",
        "setupTestDB migrations dependencies",
    ]

    parts = []
    total_calls = 0
    for q in queries:
        result = client.search(q, limit=10)
        if result and not result.startswith("[Mem0 error"):
            parts.append(f"### Search: {q}\n{result}")
            total_calls += 1

    # Also list all memories for completeness
    all_mem = client.list_all(limit=50)
    if all_mem and not all_mem.startswith("[Mem0 error"):
        parts.append(f"### All Memories\n{all_mem}")
        total_calls += 1

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

    queries = [
        ("Bean & Brew architecture Clean Architecture layers", "causal", "fact"),
        ("SQLite PostgreSQL database choice trade-off", "causal", "opinion"),
        ("TestIntegrationProductSearch flaky test ICU", "causal", "fact"),
        ("test count distribution entity repository usecase handler 637", "forward", "fact"),
        ("setupTestDB migrations dependencies break", "forward", "fact"),
    ]

    parts = []
    total_calls = 0

    for query, chain_mode, concept_type in queries:
        # search_memory
        result = client.search_memory(query, limit=10)
        if result:
            parts.append(f"### Memory: {query}\n{result}")
            total_calls += 1

        # search_reasoning_chain
        chain = client.search_reasoning_chain(query, mode=chain_mode)
        if chain:
            parts.append(f"### Reasoning Chain ({chain_mode}): {query}\n{chain}")
            total_calls += 1

        # search_by_concept
        concept = client.search_by_concept(query, concept_type=concept_type)
        if concept:
            parts.append(f"### Concept ({concept_type}): {query}\n{concept}")
            total_calls += 1

    context = "\n\n".join(parts)
    elapsed = int((time.time() - t0) * 1000)

    client.stop()
    return context, {
        "tool_calls": total_calls,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


def onboard_graphiti(context_file):
    """Graphiti fallback: same as MD but with graph-like framing."""
    t0 = time.time()
    with open(context_file) as f:
        episodes = json.load(f)
    # Simulate graph extraction: entities + relationships
    parts = []
    for ep in episodes:
        parts.append(f"[Node: {ep['name']}]\n{ep['content']}")
    context = "\n\n".join(parts)
    elapsed = int((time.time() - t0) * 1000)
    return context, {
        "tool_calls": 1,
        "retrieval_time_ms": elapsed,
        "context_chars": len(context),
        "context_tokens_est": estimate_tokens(context),
    }


APPROACHES = {
    "md_files": onboard_md_files,
    "github_issues": onboard_github_issues,
    "mem0": onboard_mem0,
    "helixir_mcp": onboard_helixir_mcp,
    "graphiti": onboard_graphiti,
}


# ─── Verification Phase ──────────────────────────────────────────────

def run_verification(context_text, run_id):
    """Ask 5 questions with retrieved context, evaluate answers."""
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
            model=EVALUATOR_MODEL, temperature=0.0, max_tokens=4000,
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
        print(f" {total}/16 ({latency}ms)")

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

    # Phase 1: Onboarding
    print(f"\n  Phase 1: Onboarding...")
    onboard_fn = APPROACHES[approach]
    if approach in ("md_files", "github_issues", "graphiti"):
        context, onboard_metrics = onboard_fn(context_file)
    else:
        context, onboard_metrics = onboard_fn()

    print(f"    Context: {onboard_metrics['context_chars']:,} chars "
          f"(~{onboard_metrics['context_tokens_est']:,} tokens)")
    print(f"    Tool calls: {onboard_metrics['tool_calls']}")
    print(f"    Retrieval time: {onboard_metrics['retrieval_time_ms']}ms")

    # Phase 2: Verification (multiple runs)
    all_runs = []
    for run_id in range(1, num_runs + 1):
        print(f"\n  Phase 2: Verification run {run_id}/{num_runs}")
        results, run_metrics = run_verification(context, run_id)
        run_total = sum(r["total"] for r in results)
        all_runs.append({
            "run_id": run_id,
            "results": results,
            "metrics": run_metrics,
            "total_score": run_total,
        })
        print(f"    Run {run_id} total: {run_total}/80")

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

    aggregate = {
        "context_tokens": onboard_metrics["context_tokens_est"],
        "verification_input_tokens": rm["total_input_tokens"],
        "verification_output_tokens": rm["total_output_tokens"],
        "total_tokens": total_input + total_output,
        "retrieval_time_ms": onboard_metrics["retrieval_time_ms"],
        "verification_time_ms": rm["total_time_ms"],
        "total_time_ms": onboard_metrics["retrieval_time_ms"] + rm["total_time_ms"],
        "tool_calls": onboard_metrics["tool_calls"],
        "messages": rm["messages"],
        "accuracy_pct": round(stats["total_median"] / 80 * 100, 1),
        "cost_estimate_usd": round(cost_estimate, 6),
        "cost_performance_ratio": round(stats["total_median"] / max(cost_estimate, 0.000001), 1),
    }

    print(f"\n  Summary: {approach}")
    print(f"    Accuracy: {aggregate['accuracy_pct']}%")
    print(f"    Total tokens: {aggregate['total_tokens']:,}")
    print(f"    Total time: {aggregate['total_time_ms']}ms")
    print(f"    Cost: ${aggregate['cost_estimate_usd']:.6f}")
    print(f"    Cost/Perf: {aggregate['cost_performance_ratio']}")

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
        "max_score": 80,
        "approaches": {},
    }

    for r in results:
        summary["approaches"][r.approach] = r.aggregate

    path = Path(output_dir) / "recovery_comparison.json"
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")

    # Print comparison table
    print(f"\n{'='*80}")
    print(f"{'Approach':<18} {'Tokens':>8} {'Time(ms)':>10} {'Accuracy':>10} {'Cost($)':>10} {'C/P Ratio':>10}")
    print(f"{'-'*80}")
    for r in results:
        a = r.aggregate
        print(f"{r.approach:<18} {a['total_tokens']:>8,} {a['total_time_ms']:>10,} "
              f"{a['accuracy_pct']:>9.1f}% ${a['cost_estimate_usd']:>9.6f} {a['cost_performance_ratio']:>10.1f}")
    print(f"{'='*80}")


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
