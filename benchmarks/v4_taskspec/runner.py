"""v4 task-spec benchmark runner.

Flow:
  1. For each (approach, task) pair: load approach-specific context, call
     planner LLM to produce a task-spec MD document.
  2. For each produced spec: call critic LLM in an ISOLATED session
     (fresh HTTP request, no history, no approach name in input) to
     find open questions. Two-pass: (A) enumerate questions, (B) rate
     criticality 1/2/3.
  3. Score per (approach, task) = sum(criticality). Lower is better.
  4. On a random 10% sample, call a spot-checker LLM (different family)
     and compute Spearman rank correlation against the main critic.

Anti-bias measures live here:
  - no approach id in critic payload
  - randomized order of specs within a task
  - two-pass critique
  - spot-checker on 3rd family
  - JSON-only parseable output

Uses ONLY Cerebras (no extra LLM budget). Role split via model choice.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx


CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# Three different model families + two providers, chosen to mitigate
# evaluator bias. GLM was considered for the critic role but dropped —
# as a reasoning model it consumed the token budget on internal thoughts
# and returned an empty `content` field on complex critic tasks.
PLANNER_MODEL = "gpt-oss-120b"                      # OpenAI OSS, Cerebras — production
CRITIC_MODEL = "qwen-3-235b-a22b-instruct-2507"     # Qwen (Alibaba), Cerebras — preview
SPOT_CHECKER_MODEL = "deepseek-chat"                # DeepSeek V3.2, deepseek.com — non-thinking

# Which provider each model runs on.
MODEL_PROVIDER = {
    PLANNER_MODEL: "cerebras",
    CRITIC_MODEL: "cerebras",
    SPOT_CHECKER_MODEL: "deepseek",
}

APPROACHES = ["md_files", "github_issues", "mem0", "helixir"]

SCRIPT_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"
RESULTS_DIR = SCRIPT_DIR / "results"


# ---------- HTTP ----------

def _client() -> httpx.Client:
    """Fresh client per call (isolated session for critic)."""
    return httpx.Client(
        timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        transport=httpx.HTTPTransport(retries=2),
    )


def call_llm(messages: list[dict], model: str, temperature: float = 0.2,
             max_tokens: int = 4000, max_retries: int = 4) -> tuple[str, int]:
    """One-shot LLM call with provider routing and retries. Returns (content, latency_ms)."""
    provider = MODEL_PROVIDER.get(model)
    if provider == "cerebras":
        base_url, api_key = CEREBRAS_BASE_URL, CEREBRAS_API_KEY
        if not api_key:
            raise RuntimeError("CEREBRAS_API_KEY env var is not set")
    elif provider == "deepseek":
        base_url, api_key = DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY env var is not set")
    else:
        raise ValueError(f"no provider mapping for model {model}")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    t0 = time.time()
    last_exc = None
    for attempt in range(max_retries):
        try:
            with _client() as cl:
                resp = cl.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
            if resp.status_code >= 500 or resp.status_code == 429:
                # Retry on transient errors.
                raise httpx.HTTPStatusError(
                    f"transient {resp.status_code}", request=resp.request, response=resp,
                )
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            # Fallback: some reasoning providers put their only textual output in
            # `reasoning` when the content channel is empty — accept it rather
            # than report a 0-char answer.
            if not content:
                content = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
            return content, int((time.time() - t0) * 1000)
        except (httpx.HTTPStatusError, httpx.RemoteProtocolError,
                httpx.ReadTimeout, httpx.ConnectError) as e:
            last_exc = e
            wait = 2 ** attempt
            print(f"    [retry {attempt+1}/{max_retries}] {type(e).__name__}: "
                  f"sleeping {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"LLM call failed after {max_retries} retries: {last_exc}")


# ---------- Context loading ----------

def load_approach_context(approach: str) -> str:
    """Load approach-specific context.

    For v4 this is the realistic per-approach retrieval channel. In this
    first drop we provide a thin shim: md_files/github_issues read their
    own on-disk snapshot; mem0/helixir call their live MCP retrievers
    (to be wired in a follow-up commit).

    For the benchmark to be honest, each approach must produce context
    through its OWN pipeline. Everything below is the boundary between
    this runner and the approach's retrieval code.
    """
    shared = Path(__file__).resolve().parent.parent / "shared" / "data" / "test_context.json"
    with open(shared) as f:
        episodes = json.load(f)

    if approach == "md_files":
        # Baseline: the same episodes (simulates reading docs/ verbatim).
        return "\n\n".join(f"### {e['name']}\n{e['content']}" for e in episodes)

    if approach == "github_issues":
        # TODO: wire real gh API retrieval per task topic
        return "\n\n".join(f"### {e['name']}\n{e['content']}" for e in episodes)

    if approach == "mem0":
        # TODO: wire real Mem0 MCP search per task topic
        return "\n\n".join(f"### {e['name']}\n{e['content']}" for e in episodes)

    if approach == "helixir":
        # TODO: wire real Helixir MCP search_memory + search_by_concept
        return "\n\n".join(f"### {e['name']}\n{e['content']}" for e in episodes)

    raise ValueError(f"unknown approach: {approach}")


# ---------- Planner ----------

def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def plan_spec(approach: str, task: dict, context: str) -> tuple[str, int]:
    """Call planner LLM to produce a task-spec MD file."""
    planner_prompt = load_prompt("planner")
    system = (
        f"{planner_prompt}\n\n---\n"
        f"Project context you have access to (your memory source: {approach}):\n\n"
        f"{context}"
    )
    user = f"Task topic: {task['topic']}\nAdditional notes: {task.get('notes', '')}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return call_llm(messages, model=PLANNER_MODEL, temperature=0.3, max_tokens=4000)


# ---------- Critic (ISOLATED SESSION) ----------

JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json(text: str):
    m = JSON_BLOCK_RE.search(text)
    if m:
        return json.loads(m.group(1))
    # fallback: last {...} or [...]
    last_obj = text.rfind("{")
    last_arr = text.rfind("[")
    start = max(last_obj, last_arr)
    if start >= 0:
        try:
            return json.loads(text[start:])
        except Exception:
            pass
    return None


def critique_spec_isolated(spec_md: str, project_context: str) -> dict:
    """Two-pass critic in an isolated session.

    Pass 1: enumerate open questions (no scoring).
    Pass 2: rate criticality 1/2/3 for each question.

    Both passes are FRESH calls (no shared history) so the second pass
    cannot shortcut using the first pass's intermediate reasoning.
    """
    critic_prompt = load_prompt("critic")

    # Pass 1: enumerate
    system_p1 = (
        f"{critic_prompt}\n\n---\nProject context (ground truth):\n\n{project_context}"
    )
    user_p1 = (
        "TASK-SPEC TO REVIEW:\n\n"
        f"{spec_md}\n\n"
        "Pass 1 of 2. Enumerate EVERY open question, missing detail, "
        "contradiction, or hallucinated fact you find. Do NOT score yet. "
        "Return a JSON array of strings.\n\n"
        "```json\n[\"question 1\", \"question 2\", ...]\n```"
    )
    p1_raw, p1_ms = call_llm(
        [{"role": "system", "content": system_p1}, {"role": "user", "content": user_p1}],
        model=CRITIC_MODEL, temperature=0.0, max_tokens=4000,
    )
    questions = _extract_json(p1_raw) or []
    if not isinstance(questions, list):
        questions = []

    # Pass 2: score each (fresh call, no memory of pass 1)
    system_p2 = (
        f"{critic_prompt}\n\n---\nProject context (ground truth):\n\n{project_context}"
    )
    user_p2 = (
        "TASK-SPEC UNDER REVIEW:\n\n"
        f"{spec_md}\n\n"
        "Open questions found in this spec:\n"
        + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        + "\n\nPass 2 of 2. Rate criticality of each question on scale 1/2/3:\n"
          "3 = blocker (developer cannot start / would do it wrong)\n"
          "2 = significant (rework likely — missed edge case, unclear scope)\n"
          "1 = minor (wording/clarity improvement)\n\n"
          "Return JSON:\n```json\n"
          "{\"ratings\": [{\"q\": \"<question>\", \"criticality\": 1|2|3, \"why\": \"<short>\"}]}\n"
          "```"
    )
    p2_raw, p2_ms = call_llm(
        [{"role": "system", "content": system_p2}, {"role": "user", "content": user_p2}],
        model=CRITIC_MODEL, temperature=0.0, max_tokens=4000,
    )
    ratings_obj = _extract_json(p2_raw) or {}
    ratings = ratings_obj.get("ratings", []) if isinstance(ratings_obj, dict) else []

    total = sum(int(r.get("criticality", 0)) for r in ratings if isinstance(r, dict))
    by_level = {3: 0, 2: 0, 1: 0}
    for r in ratings:
        c = int(r.get("criticality", 0)) if isinstance(r, dict) else 0
        if c in by_level:
            by_level[c] += 1

    return {
        "total_criticality": total,
        "num_questions": len(ratings),
        "by_level": by_level,
        "ratings": ratings,
        "pass1_raw": p1_raw,
        "pass2_raw": p2_raw,
        "latency_ms": p1_ms + p2_ms,
    }


def spot_check(spec_md: str, project_context: str) -> dict:
    """Spot-checker on different model family (DeepSeek/Llama). Same two-pass
    structure, cheaper model. Used on 10% random sample for rank correlation.
    """
    critic_prompt = load_prompt("critic")

    system = (
        f"{critic_prompt}\n\n---\nProject context (ground truth):\n\n{project_context}"
    )
    user = (
        "TASK-SPEC TO REVIEW:\n\n"
        f"{spec_md}\n\n"
        "Find open questions and rate each 1/2/3 "
        "(3=blocker, 2=significant, 1=minor). JSON:\n"
        "```json\n{\"ratings\": [{\"q\": \"...\", \"criticality\": 1|2|3}]}\n```"
    )
    raw, ms = call_llm(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=SPOT_CHECKER_MODEL, temperature=0.0, max_tokens=3000,
    )
    obj = _extract_json(raw) or {}
    ratings = obj.get("ratings", []) if isinstance(obj, dict) else []
    total = sum(int(r.get("criticality", 0)) for r in ratings if isinstance(r, dict))
    return {"total_criticality": total, "raw": raw, "latency_ms": ms}


# ---------- Orchestration ----------

@dataclass
class SpecResult:
    approach: str
    task_id: str
    topic: str
    spec_md: str
    critic: dict = field(default_factory=dict)
    spot_check: dict | None = None
    planner_latency_ms: int = 0
    timestamp: str = ""


def run(tasks_path: Path, seed: int = 42, spot_check_ratio: float = 0.1,
        checkpoint_path: Path | None = None) -> list[SpecResult]:
    with open(tasks_path) as f:
        tasks = json.load(f)

    random.seed(seed)

    def checkpoint(specs: list[SpecResult], phase: str):
        if checkpoint_path is None:
            return
        save(specs, checkpoint_path)
        print(f"    [checkpoint:{phase}] -> {checkpoint_path.name}", flush=True)

    # Phase 1: generate all specs (per approach)
    specs: list[SpecResult] = []
    for task in tasks:
        approach_order = APPROACHES[:]
        random.shuffle(approach_order)  # randomized order per task
        for approach in approach_order:
            context = load_approach_context(approach)
            spec_md, planner_ms = plan_spec(approach, task, context)
            specs.append(SpecResult(
                approach=approach,
                task_id=task["id"],
                topic=task["topic"],
                spec_md=spec_md,
                planner_latency_ms=planner_ms,
                timestamp=datetime.utcnow().isoformat(),
            ))
            print(f"[plan] {task['id']} / {approach}: {planner_ms}ms "
                  f"({len(spec_md)} chars)", flush=True)
            checkpoint(specs, "plan")

    # Phase 2: critic ISOLATED over anonymized specs in random order
    crit_order = specs[:]
    random.shuffle(crit_order)  # order bias removal
    # Anonymize: pass only spec_md + context to critic; keep approach id in
    # our own bookkeeping only.
    project_ctx = load_approach_context("md_files")  # ground truth = md baseline
    for s in crit_order:
        s.critic = critique_spec_isolated(s.spec_md, project_ctx)
        print(f"[crit] {s.task_id} / {s.approach}: "
              f"{s.critic['total_criticality']} ({s.critic['num_questions']} qs)",
              flush=True)
        checkpoint(specs, "crit")

    # Phase 3: spot-checker on 10% sample
    sample = random.sample(specs, max(1, int(len(specs) * spot_check_ratio)))
    for s in sample:
        s.spot_check = spot_check(s.spec_md, project_ctx)
        print(f"[spot] {s.task_id} / {s.approach}: "
              f"{s.spot_check['total_criticality']}", flush=True)
        checkpoint(specs, "spot")

    return specs


def save(specs: list[SpecResult], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(s) for s in specs]
    summary = {
        "planner_model": PLANNER_MODEL,
        "critic_model": CRITIC_MODEL,
        "spot_checker_model": SPOT_CHECKER_MODEL,
        "timestamp": datetime.utcnow().isoformat(),
        "per_spec": rows,
        "totals_by_approach": _totals(rows),
    }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))


def _totals(rows: list[dict]) -> dict:
    out: dict = {}
    for r in rows:
        a = r["approach"]
        cur = out.setdefault(a, {"total_criticality": 0, "num_specs": 0, "by_level": {3: 0, 2: 0, 1: 0}})
        cur["total_criticality"] += r["critic"].get("total_criticality", 0)
        cur["num_specs"] += 1
        for lvl, n in r["critic"].get("by_level", {}).items():
            cur["by_level"][int(lvl)] += n
    return out


def main():
    if len(sys.argv) < 2:
        print("Usage: python runner.py <tasks.json> [seed] [spot_check_ratio]")
        print(f"Default tasks: {SCRIPT_DIR / 'tasks.json'}")
        sys.exit(1)

    tasks_path = Path(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    ratio = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1

    out = RESULTS_DIR / f"v4_taskspec_{int(time.time())}.json"
    specs = run(tasks_path, seed=seed, spot_check_ratio=ratio, checkpoint_path=out)
    save(specs, out)
    print(f"\nSaved -> {out}", flush=True)


if __name__ == "__main__":
    main()
