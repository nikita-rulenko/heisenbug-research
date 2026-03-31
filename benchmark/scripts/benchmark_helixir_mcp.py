"""Benchmark Helixir MCP: Uses full Helixir MCP tools (search_memory, search_reasoning_chain,
search_by_concept) to build per-scenario context dynamically.

This replaces the old "helixir" approach which only used raw search_memory.
Now each scenario gets tailored context from multiple MCP tools.

Parts A + B + C all in one script, 3 runs each with v2 evaluation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import statistics
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from benchmark_runner_v2 import (
    call_llm, _extract_scores_json, evaluate_v2,
    SCENARIOS, GENERATOR_MODEL, EVALUATOR_MODEL,
)
from benchmark_part_b_v2 import GRAPH_SCENARIOS, EVAL_PROMPT_B_V2
from benchmark_part_c_v2 import DECISIONS, EVAL_PROMPT_C_V2

NUM_RUNS = 3
USER_ID = "bench"

# Helixir MCP binary and environment
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

# Scenario -> MCP strategy mapping
# For each scenario, define which tools to use and how
SCENARIO_STRATEGIES = {
    # Part A
    "S1": {"tools": ["search_memory"], "queries": ["Order CalculateTotal unit test edge cases"]},
    "S2": {"tools": ["search_memory"], "queries": ["endpoint /api/v1/products tests coverage"]},
    "S3": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["TestIntegrationProductSearch flaky"], "chain_mode": "causal"},
    "S4": {"tools": ["search_memory"], "queries": ["NewsItem entity files tests rename"]},
    "S5": {"tools": ["search_memory"], "queries": ["E2E test flow category product order complete"]},
    "S6": {"tools": ["search_memory"], "queries": ["product schema fields entity repository migration tests"]},
    "S7": {"tools": ["search_memory"], "queries": ["duplicate overlapping tests pairs"]},
    "S8": {"tools": ["search_memory", "search_by_concept"], "queries": ["test plan testing levels unit integration API"], "concept_type": "fact"},
    "S9": {"tools": ["search_memory"], "queries": ["TestUnitProductValidate price validation history"]},
    "S10": {"tools": ["search_memory"], "queries": ["test suite optimization parallel build tags table-driven"]},
    "S11": {"tools": ["search_memory"], "queries": ["test coverage matrix entity Product Order Category NewsItem layer"]},
    "S12": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["setupTestDB migration dependencies tests"], "chain_mode": "forward"},
    # Part B
    "G1": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["handler order.go entity order.go dependency layers"], "chain_mode": "both"},
    "G2": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["CategoryID Product impact entities tests endpoints"], "chain_mode": "forward"},
    "G3": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["TestIntegrationProductSearch flaky root cause fix"], "chain_mode": "causal"},
    "G4": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["TestAPIOrderFlow entities endpoints business rules helpers"], "chain_mode": "both"},
    "G5": {"tools": ["search_memory", "search_reasoning_chain"], "queries": ["test execution order dependency violation"], "chain_mode": "causal"},
    # Part C
    "D1": {"tools": ["search_memory", "search_reasoning_chain", "search_by_concept"], "queries": ["Clean Architecture 4 layers decision rationale alternatives"], "chain_mode": "causal", "concept_type": "opinion"},
    "D2": {"tools": ["search_memory", "search_reasoning_chain", "search_by_concept"], "queries": ["table-driven tests t.Run decision rationale"], "chain_mode": "causal", "concept_type": "opinion"},
    "D3": {"tools": ["search_memory", "search_reasoning_chain", "search_by_concept"], "queries": ["TestIntegrationProductSearch flaky keep decision trade-off ICU"], "chain_mode": "causal", "concept_type": "opinion"},
    "D4": {"tools": ["search_memory", "search_reasoning_chain", "search_by_concept"], "queries": ["SQLite PostgreSQL decision rationale trade-off"], "chain_mode": "causal", "concept_type": "opinion"},
    "D5": {"tools": ["search_memory", "search_reasoning_chain", "search_by_concept"], "queries": ["usecase tests real DB mocks decision rationale"], "chain_mode": "causal", "concept_type": "opinion"},
}


class HelixirMCPClient:
    """Communicates with helixir-mcp binary via JSON-RPC over stdio."""

    def __init__(self):
        self.proc = None
        self._msg_id = 0

    def start(self):
        self.proc = subprocess.Popen(
            [HELIXIR_MCP_BIN],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=HELIXIR_ENV,
        )
        # Send initialize
        resp = self._send_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "benchmark", "version": "1.0"}
        })
        # Send initialized notification
        self._send_notification("notifications/initialized", {})
        return resp

    def stop(self):
        if self.proc:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    def _next_id(self):
        self._msg_id += 1
        return self._msg_id

    def _send_rpc(self, method, params):
        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        raw = json.dumps(msg) + "\n"
        self.proc.stdin.write(raw.encode())
        self.proc.stdin.flush()

        # Read response line
        line = self.proc.stdout.readline().decode().strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _send_notification(self, method, params):
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        raw = json.dumps(msg) + "\n"
        self.proc.stdin.write(raw.encode())
        self.proc.stdin.flush()

    def call_tool(self, tool_name, arguments):
        resp = self._send_rpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if resp and "result" in resp:
            content = resp["result"].get("content", [])
            texts = []
            for item in content:
                if item.get("type") == "text":
                    texts.append(item["text"])
            return "\n".join(texts)
        elif resp and "error" in resp:
            return f"[ERROR: {resp['error']}]"
        return ""

    def search_memory(self, query, mode="full", limit=15):
        return self.call_tool("search_memory", {
            "query": query,
            "user_id": USER_ID,
            "mode": mode,
            "limit": limit,
        })

    def search_reasoning_chain(self, query, chain_mode="causal", max_depth=3):
        return self.call_tool("search_reasoning_chain", {
            "query": query,
            "user_id": USER_ID,
            "chain_mode": chain_mode,
            "max_depth": max_depth,
        })

    def search_by_concept(self, query, concept_type="fact"):
        return self.call_tool("search_by_concept", {
            "query": query,
            "user_id": USER_ID,
            "concept_type": concept_type,
            "limit": 10,
        })


def build_context_for_scenario(client, scenario_id, query_text):
    """Build rich context using multiple Helixir MCP tools based on strategy."""
    strategy = SCENARIO_STRATEGIES.get(scenario_id, {
        "tools": ["search_memory"],
        "queries": [query_text],
    })

    parts = []
    search_query = strategy.get("queries", [query_text])[0]

    # Always do search_memory first
    if "search_memory" in strategy["tools"]:
        result = client.search_memory(search_query, mode="full", limit=15)
        if result:
            parts.append(f"### Memory Search Results\n{result}")

    # Add reasoning chain if applicable
    if "search_reasoning_chain" in strategy["tools"]:
        chain_mode = strategy.get("chain_mode", "causal")
        result = client.search_reasoning_chain(search_query, chain_mode=chain_mode, max_depth=3)
        if result:
            parts.append(f"### Reasoning Chain ({chain_mode})\n{result}")

    # Add concept search if applicable
    if "search_by_concept" in strategy["tools"]:
        concept_type = strategy.get("concept_type", "fact")
        result = client.search_by_concept(search_query, concept_type=concept_type)
        if result:
            parts.append(f"### Concept Search ({concept_type})\n{result}")

    return "\n\n".join(parts) if parts else "[No context retrieved]"


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    part: str = ""
    answer: str = ""
    context_text: str = ""
    context_chars: int = 0
    latency_ms: int = 0
    scores: dict = field(default_factory=dict)
    total: int = 0
    evaluator_reasoning: str = ""


@dataclass
class RunResult:
    run_id: int
    part: str = ""
    scenarios: list = field(default_factory=list)
    total: int = 0
    timestamp: str = ""


def evaluate_b_v2(answer, gold):
    prompt = EVAL_PROMPT_B_V2.format(gold=gold, answer=answer)
    content, reasoning, _ = call_llm(
        [{"role": "user", "content": prompt}],
        model=EVALUATOR_MODEL, temperature=0.0, max_tokens=8000,
    )
    keys = ["accuracy", "completeness", "context_utilization", "actionability"]
    for source in [content, reasoning]:
        if not source:
            continue
        scores = _extract_scores_json(source)
        if scores:
            return scores, reasoning
    fallback = {k: 0 for k in keys}
    fallback["total"] = 0
    fallback["reasoning_summary"] = f"Parse fail: content={content[:200]}"
    return fallback, reasoning


def evaluate_c_v2(answer, gold):
    prompt = EVAL_PROMPT_C_V2.format(gold=gold, answer=answer)
    content, reasoning, _ = call_llm(
        [{"role": "user", "content": prompt}],
        model=EVALUATOR_MODEL, temperature=0.0, max_tokens=8000,
    )
    keys = ["accuracy", "completeness", "context_utilization", "actionability"]
    for source in [content, reasoning]:
        if not source:
            continue
        scores = _extract_scores_json(source)
        if scores:
            return scores, reasoning
    fallback = {k: 0 for k in keys}
    fallback["total"] = 0
    fallback["reasoning_summary"] = f"Parse fail: content={content[:200]}"
    return fallback, reasoning


def run_part(client, part, scenarios, eval_fn, run_id, system_suffix=""):
    """Run one part (A/B/C) for one run."""
    results = []
    for s in scenarios:
        sid = s["id"]
        # Part C uses "question" and "decision", Parts A/B use "prompt" and "name"
        prompt_text = s.get("prompt", s.get("question", ""))
        scenario_name = s.get("name", s.get("decision", ""))
        print(f"  R{run_id} [{sid}] {scenario_name[:50]}...", end="", flush=True)

        # Build dynamic context via Helixir MCP
        context_text = build_context_for_scenario(client, sid, prompt_text)

        system_msg = (
            "You are an AI assistant helping with the Bean & Brew Go coffee shop project.\n\n"
            f"Here is the project context retrieved from Helixir memory system:\n\n{context_text}\n\n"
            "Answer questions about the project based ONLY on this context. "
            f"Be specific: reference real test names, file paths, and function signatures.{system_suffix}"
        )

        answer, _, latency = call_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt_text}
        ])

        gold = s.get("gold", s.get("reasoning", ""))
        scores, eval_reasoning = eval_fn(answer, gold)
        total = scores.get("total", 0)

        r = ScenarioResult(
            scenario_id=sid,
            scenario_name=scenario_name,
            part=part,
            answer=answer,
            context_text=context_text[:500],  # truncate for storage
            context_chars=len(context_text),
            latency_ms=latency,
            scores=scores,
            total=total,
            evaluator_reasoning=eval_reasoning[:500],
        )
        results.append(r)
        print(f" {total}/16 ({latency}ms, ctx={len(context_text):,}ch)")

    run_total = sum(r.total for r in results)
    return RunResult(
        run_id=run_id,
        part=part,
        scenarios=results,
        total=run_total,
        timestamp=datetime.now().isoformat(),
    )


def compute_stats(runs):
    scenario_ids = [s.scenario_id for s in runs[0].scenarios]
    stats = {}
    for sid in scenario_ids:
        scores_per_run = []
        for run in runs:
            for s in run.scenarios:
                if s.scenario_id == sid:
                    scores_per_run.append(s.total)
                    break
        stats[sid] = {
            "scores": scores_per_run,
            "median": statistics.median(scores_per_run),
            "mean": round(statistics.mean(scores_per_run), 2),
            "stddev": round(statistics.stdev(scores_per_run), 2) if len(scores_per_run) > 1 else 0,
        }
    totals = [r.total for r in runs]
    stats["overall"] = {
        "scores": totals,
        "median": statistics.median(totals),
        "mean": round(statistics.mean(totals), 2),
        "stddev": round(statistics.stdev(totals), 2) if len(totals) > 1 else 0,
        "min": min(totals),
        "max": max(totals),
    }
    return stats


def save_results(part, runs, stats, max_per_scenario=16, num_scenarios=None):
    n = num_scenarios or len(runs[0].scenarios)
    max_total = max_per_scenario * n
    median_total = stats["overall"]["median"]

    data = {
        "version": "2.0",
        "part": part,
        "approach": "helixir_mcp",
        "timestamp": datetime.now().isoformat(),
        "generator_model": GENERATOR_MODEL,
        "evaluator_model": EVALUATOR_MODEL,
        "num_runs": len(runs),
        "num_scenarios": n,
        "scoring": {"scale": "1-4", "criteria": 4, "max_per_scenario": max_per_scenario, "max_total": max_total},
        "statistics": stats,
        "median_total": median_total,
        "median_percentage": round(median_total / max_total * 100, 1),
        "mcp_tools_used": ["search_memory", "search_reasoning_chain", "search_by_concept"],
        "runs": [
            {
                "run_id": r.run_id,
                "total": r.total,
                "timestamp": r.timestamp,
                "scenarios": [asdict(s) for s in r.scenarios],
            }
            for r in runs
        ],
    }

    suffix = {"A": "", "B": "_part_b", "C": "_part_c"}[part]
    path = f"results_v2_helixir_mcp{suffix}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*60}")
    print(f"Part {part} results saved to {path}")
    print(f"  Median: {median_total}/{max_total} ({data['median_percentage']}%)")
    print(f"  Mean: {stats['overall']['mean']} +/- {stats['overall']['stddev']}")
    return data


def main():
    parts = sys.argv[1].upper().split(",") if len(sys.argv) > 1 else ["A", "B", "C"]
    num_runs = int(sys.argv[2]) if len(sys.argv) > 2 else NUM_RUNS

    print(f"\n{'='*60}")
    print(f"Benchmark Helixir MCP (full tools)")
    print(f"  Parts: {', '.join(parts)}")
    print(f"  Generator: {GENERATOR_MODEL} | Evaluator: {EVALUATOR_MODEL}")
    print(f"  Runs: {num_runs}")
    print(f"  MCP tools: search_memory + search_reasoning_chain + search_by_concept")
    print(f"{'='*60}\n")

    # Start MCP client
    print("Starting Helixir MCP server...", end="", flush=True)
    client = HelixirMCPClient()
    init_resp = client.start()
    print(f" OK")

    try:
        for part in parts:
            if part == "A":
                scenarios = SCENARIOS
                eval_fn = evaluate_v2
                suffix = ""
                n = len(SCENARIOS)
            elif part == "B":
                scenarios = GRAPH_SCENARIOS
                eval_fn = evaluate_b_v2
                suffix = "\nTrace connections between layers, entities, and tests precisely."
                n = len(GRAPH_SCENARIOS)
            elif part == "C":
                scenarios = DECISIONS
                eval_fn = evaluate_c_v2
                suffix = ("\nWhen asked about decisions, provide: "
                         "1) The decision itself, 2) The reasoning/rationale, "
                         "3) Alternatives considered and why rejected, "
                         "4) Trade-offs accepted.")
                n = len(DECISIONS)
            else:
                print(f"Unknown part: {part}")
                continue

            print(f"\n{'='*60}")
            print(f"Part {part}: {n} scenarios, {num_runs} runs, max {16 * n}/run")
            print(f"{'='*60}")

            runs = []
            for i in range(1, num_runs + 1):
                print(f"\n--- Part {part} Run {i}/{num_runs} ---")
                run = run_part(client, part, scenarios, eval_fn, i, suffix)
                runs.append(run)
                print(f"  Run {i} total: {run.total}/{16 * n}")

            stats = compute_stats(runs)
            save_results(part, runs, stats, num_scenarios=n)

    finally:
        client.stop()
        print("\nHelixir MCP server stopped.")


if __name__ == "__main__":
    main()
