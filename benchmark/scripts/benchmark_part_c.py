"""Benchmark Part C: Decision Reasoning — can systems store and retrieve the WHY behind decisions."""
from __future__ import annotations

import json
import os
import time
from benchmark_runner import call_cerebras, ScenarioResult

_script_dir = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.path.join(os.path.dirname(_script_dir), "data")
_decision_path = os.path.join(_data_dir, "decision_context.json")
if not os.path.exists(_decision_path):
    _decision_path = "decision_context.json"
with open(_decision_path) as f:
    DECISIONS = json.load(f)

EVAL_PROMPT_C = """You are an expert evaluator for decision reasoning retrieval. Score the ANSWER on 5 criteria (0-5 each):

1. **Rationale Recovery**: Does the answer contain the original reasoning, not just the decision itself?
2. **Alternatives Mentioned**: Are rejected alternatives explicitly named?
3. **Trade-offs Articulated**: Are accepted downsides/costs mentioned?
4. **No Fabricated Reasoning**: Is the reasoning sourced from stored context (not hallucinated)?
5. **Decision Traceability**: Can the answer be traced back to a specific decision point with clear cause-effect?

GOLD STANDARD:
{gold}

ACTUAL ANSWER:
{answer}

Return JSON ONLY:
{{"rationale_recovery": X, "alternatives_mentioned": X, "tradeoffs_articulated": X, "no_fabricated_reasoning": X, "decision_traceability": X, "total": X, "brief_comment": "..."}}"""

SCORE_KEYS = [
    "rationale_recovery", "alternatives_mentioned", "tradeoffs_articulated",
    "no_fabricated_reasoning", "decision_traceability",
]


def evaluate_c(answer: str, gold: str) -> dict:
    prompt = EVAL_PROMPT_C.format(gold=gold, answer=answer)
    raw, _ = call_cerebras([{"role": "user", "content": prompt}], temperature=0.0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {k: 0 for k in SCORE_KEYS} | {"total": 0, "brief_comment": f"Parse fail: {raw[:200]}"}


def run_part_c(approach: str, context: str, extra_meta: dict | None = None):
    system_msg = f"""You are an AI assistant helping with the Bean & Brew Go coffee shop project.

Here is the project context (including architectural decisions and their reasoning):

{context}

When asked about decisions, provide:
1. The decision itself
2. The reasoning/rationale behind it
3. Alternatives that were considered and why they were rejected
4. Trade-offs that were accepted

Answer based ONLY on the provided context."""

    results = []
    for d in DECISIONS:
        sid = d["id"]
        print(f"  [{sid}] {d['decision'][:50]}...", end="", flush=True)
        answer, latency = call_cerebras([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": d["question"]},
        ])
        scores = evaluate_c(answer, d["gold"])
        total = sum(scores.get(k, 0) for k in SCORE_KEYS)
        r = ScenarioResult(sid, d["decision"], answer, latency, scores, total)
        results.append(r)
        print(f" {total}/25 ({latency}ms)")

    total_score = sum(r.total for r in results)
    data = {
        "approach": approach,
        "part": "C",
        "total_score": total_score,
        "max_score": 125,
        "percentage": round(total_score / 125 * 100, 1),
        "extra": extra_meta or {},
        "scenarios": [
            {"id": r.scenario_id, "name": r.scenario_name, "total": r.total,
             "latency_ms": r.latency_ms, "scores": r.scores}
            for r in results
        ],
    }
    path = f"results_{approach}_part_c.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*60}")
    print(f"Part C: {total_score}/125 ({data['percentage']}%) -> {path}")
    return data


if __name__ == "__main__":
    import sys

    approach = sys.argv[1] if len(sys.argv) > 1 else "test"
    context_file = sys.argv[2] if len(sys.argv) > 2 else None

    if context_file:
        with open(context_file) as f:
            content = f.read()
        if context_file.endswith(".json"):
            eps = json.loads(content)
            ctx = "\n\n".join(f"### {e['name']}\n{e['content']}" for e in eps)
        else:
            ctx = content
    else:
        with open("test_context.json") as f:
            eps = json.load(f)
        ctx = "\n\n".join(f"### {e['name']}\n{e['content']}" for e in eps)

    print(f"\n Part C benchmark: {approach} ({len(ctx)} chars)\n")
    run_part_c(approach, ctx)
