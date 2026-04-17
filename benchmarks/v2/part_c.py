"""Benchmark Part C v2: Decision Reasoning — separate evaluator, 3 runs.

Generator: Cerebras gpt-oss-120b
Evaluator: Cerebras zai-glm-4.7 (GLM 4.7 MoE 358B/32B active)

Scoring: 1-4 scale, 4 criteria, 5 scenarios = 80 max per run.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from runner import (
    call_llm, _extract_scores_json,
    GENERATOR_MODEL, EVALUATOR_MODEL,
)

NUM_RUNS = 3

# Load decisions
_script_dir = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.path.join(os.path.dirname(_script_dir), "shared", "data")
_decision_path = os.path.join(_data_dir, "decision_context.json")
if not os.path.exists(_decision_path):
    _decision_path = "decision_context.json"
with open(_decision_path) as f:
    DECISIONS = json.load(f)

EVAL_PROMPT_C_V2 = """You are an expert evaluator for decision reasoning retrieval. Your job is to assess whether an AI assistant correctly recovers the rationale behind architectural decisions.

IMPORTANT BIAS DISCLAIMERS:
- Do NOT prefer longer answers over shorter ones.
- Score based on CONTENT, not on formatting or presentation style.
- If the answer partially matches the gold standard, give partial credit proportionally.

Score the ANSWER on 4 criteria using a 1-4 scale:
1 = Incorrect/Missing, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct

Criteria:
1. **Accuracy** (1-4): Is the rationale correct? Does it match the actual reasoning, not hallucinated?
2. **Completeness** (1-4): Are ALL key points covered — alternatives, trade-offs, reasoning chain?
3. **Context Utilization** (1-4): Does the answer reference real project specifics (not generic advice)?
4. **Actionability** (1-4): Can someone use this answer to understand and defend the decision?

GOLD STANDARD (reference answer):
{gold}

ANSWER TO EVALUATE:
{answer}

First reason step-by-step about each criterion, then return your final scores.
You MUST end your response with a JSON block (and nothing after it):
```json
{{"accuracy": X, "completeness": X, "context_utilization": X, "actionability": X, "total": X, "reasoning_summary": "..."}}
```"""


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    answer: str = ""
    latency_ms: int = 0
    scores: dict = field(default_factory=dict)
    total: int = 0
    evaluator_reasoning: str = ""


@dataclass
class RunResult:
    run_id: int
    scenarios: list = field(default_factory=list)
    total: int = 0
    timestamp: str = ""


def evaluate_c_v2(answer: str, gold: str) -> tuple[dict, str]:
    """Use GLM 4.7 as judge for Part C."""
    prompt = EVAL_PROMPT_C_V2.format(gold=gold, answer=answer)
    content, reasoning, _ = call_llm(
        [{"role": "user", "content": prompt}],
        model=EVALUATOR_MODEL,
        temperature=0.0,
        max_tokens=8000,
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
    fallback["reasoning_summary"] = f"Parse fail: content={content[:200]}, reasoning={reasoning[:200]}"
    return fallback, reasoning


def run_single_c(approach: str, context_text: str, run_id: int) -> RunResult:
    system_msg = (
        "You are an AI assistant helping with the Bean & Brew Go coffee shop project.\n\n"
        f"Here is the project context (including architectural decisions and their reasoning):\n\n{context_text}\n\n"
        "When asked about decisions, provide:\n"
        "1. The decision itself\n"
        "2. The reasoning/rationale behind it\n"
        "3. Alternatives that were considered and why they were rejected\n"
        "4. Trade-offs that were accepted\n\n"
        "Answer based ONLY on the provided context."
    )

    results = []
    for d in DECISIONS:
        sid = d["id"]
        print(f"  R{run_id} [{sid}] {d['decision'][:50]}...", end="", flush=True)
        answer, _, latency = call_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": d["question"]},
        ])
        scores, eval_reasoning = evaluate_c_v2(answer, d["gold"])
        total = scores.get("total", 0)
        r = ScenarioResult(
            scenario_id=sid,
            scenario_name=d["decision"],
            answer=answer,
            latency_ms=latency,
            scores=scores,
            total=total,
            evaluator_reasoning=eval_reasoning[:500],
        )
        results.append(r)
        print(f" {total}/16 ({latency}ms)")

    run_total = sum(r.total for r in results)
    return RunResult(
        run_id=run_id,
        scenarios=results,
        total=run_total,
        timestamp=datetime.now().isoformat(),
    )


def compute_stats(runs: list[RunResult]) -> dict:
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


def save_results(approach: str, runs: list[RunResult], stats: dict):
    max_per_scenario = 16
    max_total = max_per_scenario * len(DECISIONS)
    median_total = stats["overall"]["median"]

    data = {
        "version": "2.0",
        "part": "C",
        "approach": approach,
        "timestamp": datetime.now().isoformat(),
        "generator_model": GENERATOR_MODEL,
        "evaluator_model": EVALUATOR_MODEL,
        "num_runs": len(runs),
        "num_scenarios": len(DECISIONS),
        "scoring": {"scale": "1-4", "criteria": 4, "max_per_scenario": max_per_scenario, "max_total": max_total},
        "statistics": stats,
        "median_total": median_total,
        "median_percentage": round(median_total / max_total * 100, 1),
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

    path = f"results_v2_{approach}_part_c.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*60}")
    print(f"Part C v2 results saved to {path}")
    print(f"  Median: {median_total}/{max_total} ({data['median_percentage']}%)")
    print(f"  Mean: {stats['overall']['mean']} +/- {stats['overall']['stddev']}")
    print(f"  Range: {stats['overall']['min']} - {stats['overall']['max']}")
    return data


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python part_c.py <approach> [context_file] [num_runs]")
        sys.exit(1)

    approach = sys.argv[1]
    context_file = sys.argv[2] if len(sys.argv) > 2 else "../shared/data/test_context.json"
    num_runs = int(sys.argv[3]) if len(sys.argv) > 3 else NUM_RUNS

    ctx_path = Path(context_file)
    if not ctx_path.exists():
        ctx_path = Path(__file__).parent / context_file
    if not ctx_path.exists():
        ctx_path = Path(__file__).parent.parent / "shared" / "data" / "test_context.json"

    with open(ctx_path) as f:
        episodes = json.load(f)
    context_text = "\n\n".join(f"### {ep['name']}\n{ep['content']}" for ep in episodes)

    # Append decision context
    decision_text = "\n\n### Architectural Decisions\n"
    for d in DECISIONS:
        decision_text += f"\n**{d['decision']}**: {d['reasoning']}\n"
    context_text += decision_text

    print(f"\n{'='*60}")
    print(f"Benchmark Part C v2: {approach}")
    print(f"  Context: {len(context_text):,} chars")
    print(f"  Generator: {GENERATOR_MODEL} | Evaluator: {EVALUATOR_MODEL}")
    print(f"  Runs: {num_runs} | Decisions: {len(DECISIONS)} | Max: {16 * len(DECISIONS)}/run")
    print(f"{'='*60}\n")

    runs = []
    for i in range(1, num_runs + 1):
        print(f"\n--- Run {i}/{num_runs} ---")
        run = run_single_c(approach, context_text, i)
        runs.append(run)
        print(f"  Run {i} total: {run.total}/{16 * len(DECISIONS)}")

    stats = compute_stats(runs)
    save_results(approach, runs, stats)


if __name__ == "__main__":
    main()
