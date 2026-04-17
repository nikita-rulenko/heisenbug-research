"""Run benchmark with MD files context."""
from runner import SCENARIOS, call_cerebras, evaluate, ScenarioResult, save_results

with open("/tmp/md_context.txt") as f:
    context = f.read()

print(f"\n🔬 Running benchmark: md_files")
print(f"   Context: {len(context)} chars from AGENTS.md + docs/")
print(f"   Model: gpt-oss-120b\n")

system_msg = f"""You are an AI assistant helping with the Bean & Brew Go coffee shop project.
You have access to the following project documentation:

{context}

Answer questions about the project based ONLY on this documentation. Be specific and reference actual test names, file paths, and code patterns from the docs."""

results = []
for s in SCENARIOS:
    print(f"  [{s['id']}] {s['name']}...", end="", flush=True)
    answer, latency = call_cerebras([
        {"role": "system", "content": system_msg},
        {"role": "user", "content": s["prompt"]}
    ])
    scores = evaluate(answer, s["gold"])
    total = sum(scores.get(k, 0) for k in ["accuracy", "completeness", "no_hallucination", "context_utilization", "actionability"])
    r = ScenarioResult(s["id"], s["name"], answer, latency, scores, total)
    results.append(r)
    print(f" {total}/25 ({latency}ms)")

save_results("md_files", results, {"context_chars": len(context), "context_source": "AGENTS.md + docs/"})
