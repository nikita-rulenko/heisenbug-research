"""Run Part B benchmark for all 5 approaches sequentially."""

import json
import time
import subprocess
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from part_b import GRAPH_SCENARIOS, run_part_b, call_cerebras, evaluate_b, ScenarioResult

INFRA = os.path.dirname(os.path.abspath(__file__))
RESULTS = {}


def bench_md_files():
    print("\n" + "=" * 60)
    print("1/5  MD FILES")
    print("=" * 60)
    with open("/tmp/md_context.txt") as f:
        ctx = f.read()
    return run_part_b("md_files", ctx)


def bench_github_issues():
    print("\n" + "=" * 60)
    print("2/5  GITHUB ISSUES")
    print("=" * 60)
    with open("/tmp/gh_issues_context.txt") as f:
        ctx = f.read()
    return run_part_b("github_issues", ctx)


def bench_mem0():
    """Mem0: for each scenario, search relevant memories, then ask LLM."""
    print("\n" + "=" * 60)
    print("3/5  MEM0 (semantic search per scenario)")
    print("=" * 60)

    import httpx
    MEM0_URL = "http://localhost:8080"

    results = []
    search_latencies = []

    for s in GRAPH_SCENARIOS:
        print(f"  [{s['id']}] {s['name']}...", end="", flush=True)

        t_search = time.time()
        try:
            resp = httpx.post(f"{MEM0_URL}/v1/memories/search/",
                              json={"query": s["prompt"], "user_id": "bench", "limit": 10},
                              timeout=30)
            resp.raise_for_status()
            memories = resp.json().get("results", resp.json()) if isinstance(resp.json(), list) else resp.json().get("results", [])
            if isinstance(resp.json(), list):
                memories = resp.json()
        except Exception as e:
            print(f" search error: {e}")
            memories = []
        search_ms = int((time.time() - t_search) * 1000)
        search_latencies.append(search_ms)

        if memories:
            ctx_parts = []
            for m in memories:
                text = m.get("memory", m.get("text", str(m)))
                ctx_parts.append(text)
            ctx = "\n\n".join(ctx_parts)
        else:
            ctx = "(no memories found)"

        system_msg = f"""You are an AI assistant helping with the Bean & Brew Go coffee shop project.
Retrieved memories:
{ctx}

Trace connections precisely. Answer based ONLY on the memories above."""

        answer, latency = call_cerebras([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": s["prompt"]}
        ])
        scores = evaluate_b(answer, s["gold"])
        total = sum(scores.get(k, 0) for k in ["hop_accuracy", "chain_completeness",
                    "no_hallucinated_links", "structural_awareness", "actionability"])
        scores["search_latency_ms"] = search_ms
        r = ScenarioResult(s["id"], s["name"], answer, latency, scores, total)
        results.append(r)
        print(f" {total}/25 (search:{search_ms}ms, llm:{latency}ms)")

    total_score = sum(r.total for r in results)
    sorted_latencies = sorted(search_latencies)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    data = {
        "approach": "mem0", "part": "B",
        "total_score": total_score, "max_score": 125,
        "percentage": round(total_score / 125 * 100, 1),
        "search_metrics": {"p50_ms": p50, "p95_ms": p95, "all_ms": search_latencies},
        "scenarios": [{"id": r.scenario_id, "name": r.scenario_name, "total": r.total,
                       "latency_ms": r.latency_ms, "scores": r.scores} for r in results],
    }
    path = os.path.join(INFRA, "results_mem0_part_b.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Mem0 Part B: {total_score}/125 ({data['percentage']}%)")
    print(f"   Search: p50={p50}ms p95={p95}ms")
    return data


def bench_helixir():
    """Helixir local: search via MCP for each scenario."""
    print("\n" + "=" * 60)
    print("4/4  HELIXIR LOCAL (semantic search per scenario)")
    print("=" * 60)

    HELIXIR_MCP = "/Users/nikitarulenko/Documents/PROJ/helixir-rs/helixir/target/release/helixir-mcp"
    env = {
        **os.environ,
        "HELIX_PORT": "6970",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "EMBEDDING_MODEL": "nomic-embed-text",
    }

    results = []
    search_latencies = []

    for s in GRAPH_SCENARIOS:
        print(f"  [{s['id']}] {s['name']}...", end="", flush=True)

        t_search = time.time()
        try:
            init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2024-11-05",
                                              "capabilities": {},
                                              "clientInfo": {"name": "bench", "version": "1.0"}}})
            notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
            search_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                     "params": {"name": "search_memory",
                                                "arguments": {"query": s["prompt"], "n_results": 10}}})
            input_data = f"{init_msg}\n{notif}\n{search_msg}\n"

            proc = subprocess.run([HELIXIR_MCP], input=input_data, capture_output=True,
                                  text=True, timeout=30, env=env)
            search_ms = int((time.time() - t_search) * 1000)
            search_latencies.append(search_ms)

            memories = []
            for line in proc.stdout.strip().split("\n"):
                try:
                    msg = json.loads(line)
                    if msg.get("id") == 2:
                        content = msg.get("result", {}).get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                memories.append(c.get("text", ""))
                        elif isinstance(content, dict):
                            memories.append(content.get("text", ""))
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f" search error: {e}")
            memories = []
            search_ms = 0
            search_latencies.append(0)

        ctx = "\n\n".join(memories) if memories else "(no memories found)"
        system_msg = f"""You are an AI assistant helping with the Bean & Brew Go coffee shop project.
Retrieved memories from Helixir:
{ctx}

Trace connections precisely. Answer based ONLY on the memories above."""

        answer, latency = call_cerebras([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": s["prompt"]}
        ])
        scores = evaluate_b(answer, s["gold"])
        total = sum(scores.get(k, 0) for k in ["hop_accuracy", "chain_completeness",
                    "no_hallucinated_links", "structural_awareness", "actionability"])
        scores["search_latency_ms"] = search_ms
        r = ScenarioResult(s["id"], s["name"], answer, latency, scores, total)
        results.append(r)
        print(f" {total}/25 (search:{search_ms}ms, llm:{latency}ms)")

    total_score = sum(r.total for r in results)
    sorted_latencies = sorted(search_latencies)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    data = {
        "approach": "helixir_local", "part": "B",
        "total_score": total_score, "max_score": 125,
        "percentage": round(total_score / 125 * 100, 1),
        "search_metrics": {"p50_ms": p50, "p95_ms": p95, "all_ms": search_latencies},
        "scenarios": [{"id": r.scenario_id, "name": r.scenario_name, "total": r.total,
                       "latency_ms": r.latency_ms, "scores": r.scores} for r in results],
    }
    path = os.path.join(INFRA, "results_helixir_local_part_b.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Helixir Part B: {total_score}/125 ({data['percentage']}%)")
    print(f"   Search: p50={p50}ms p95={p95}ms")
    return data


if __name__ == "__main__":
    all_results = {}

    all_results["md_files"] = bench_md_files()
    all_results["github_issues"] = bench_github_issues()

    print("\n⚠️  Mem0 requires running containers (docker compose up in infra/mem0)")
    try:
        import httpx
        resp = httpx.get("http://localhost:8080/v1/memories/", timeout=5,
                         params={"user_id": "bench"})
        if resp.status_code == 200:
            all_results["mem0"] = bench_mem0()
        else:
            print("   Mem0 not available, skipping")
    except Exception:
        print("   Mem0 not available, skipping")

    if os.path.exists("/Users/nikitarulenko/Documents/PROJ/helixir-rs/helixir/target/release/helixir-mcp"):
        try:
            proc = subprocess.run(["curl", "-sf", "http://localhost:6970/health"], capture_output=True, timeout=5)
            if proc.returncode == 0:
                all_results["helixir"] = bench_helixir()
            else:
                print("\n⚠️  Helixir local not running on port 6970, skipping")
        except Exception:
            print("\n⚠️  Helixir local health check failed, skipping")
    else:
        print("\n⚠️  Helixir MCP binary not found, skipping")

    print("\n" + "=" * 60)
    print("PART B SUMMARY")
    print("=" * 60)
    print(f"{'Approach':<20} {'Score':>8} {'%':>8}")
    print("-" * 40)
    for name, data in all_results.items():
        print(f"{name:<20} {data['total_score']:>5}/125 {data['percentage']:>7}%")
