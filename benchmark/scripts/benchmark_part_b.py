"""Benchmark Part B: Connectivity and search quality scenarios."""
from __future__ import annotations

import json
import time
from benchmark_runner import call_cerebras, evaluate, ScenarioResult, save_results

GRAPH_SCENARIOS = [
    {
        "id": "G1",
        "name": "Multi-hop dependency trace",
        "prompt": "Покажи полную цепочку зависимостей от handler/order.go до entity/order.go через все слои. Какие тесты покрывают каждый слой?",
        "gold": "handler/order.go → OrderUsecase (usecase/order.go) → OrderRepository (repository/sqlite/order.go) → Order entity (entity/order.go). Тесты: TestAPIOrderFlow/Cancel/Complete → TestUsecaseOrderCreate/Cancel → TestIntegrationOrderCRUD/StatusUpdate/CancelFlow/CompleteFlow → TestUnitOrderCalculateTotal/CanCancel/CanComplete/Validate."
    },
    {
        "id": "G2",
        "name": "Cross-entity impact",
        "prompt": "Если удалить поле CategoryID из Product — какие сущности, тесты и API endpoints это затронет? Проследи все связи.",
        "gold": "entity/product.go (Validate), repository/sqlite/product.go (INSERT/UPDATE/Scan), handler/product.go (JSON), TestUnitProductValidate, TestIntegrationProductCRUD, TestAPIProductCRUD, TestAPIOrderFlow (создаёт product с CategoryID), seed.go. Не затронет: news, order (кроме OrderFlow)."
    },
    {
        "id": "G3",
        "name": "Causal chain: flaky → root cause → fix",
        "prompt": "TestIntegrationProductSearch flaky. Проследи цепочку: root cause → какие ещё тесты уязвимы к той же причине → как исправить системно.",
        "gold": "Root cause: shared in-memory SQLite + LIKE с кириллицей. Уязвимы: все Integration тесты с setupTestDB() без изоляции. Решение: отдельная DB для каждого теста, или t.Cleanup с truncate, или build tag."
    },
    {
        "id": "G4",
        "name": "Inverse lookup: test → what it validates",
        "prompt": "Для теста TestAPIOrderFlow — перечисли ВСЕ сущности, endpoints, бизнес-правила и helper-функции, которые он косвенно валидирует.",
        "gold": "Entities: Category, Product, Order, OrderItem. Endpoints: POST /categories, POST /products, POST /orders. Бизнес-правила: Order.CalculateTotal, Product.Validate, Order.Validate. Helpers: setupTestServer, respondJSON, parseID. Косвенно: migrations.go, seed.go."
    },
    {
        "id": "G5",
        "name": "Contradiction detection",
        "prompt": "В проекте есть правило: тесты не должны зависеть от порядка выполнения. Найди все тесты, которые нарушают это правило.",
        "gold": "TestIntegrationProductSearch (порядок INSERT), TestIntegrationSeedData (seed), TestAPIOrderFlow (последовательность POST — но E2E, допустимо). Usecase-тесты с real DB потенциально зависят."
    }
]

EVAL_PROMPT_B = """You are an expert evaluator for graph-based reasoning. Score the ANSWER on 5 criteria (0-5 each):

1. **Hop Accuracy**: Are the connections between layers/entities traced correctly?
2. **Chain Completeness**: Are ALL links in the chain found?
3. **No Hallucinated Links**: Are there any made-up connections?
4. **Structural Awareness**: Does the answer show understanding of architecture layers and dependency directions?
5. **Actionability**: Can you act on this answer directly?

GOLD STANDARD:
{gold}

ACTUAL ANSWER:
{answer}

Return JSON ONLY:
{{"hop_accuracy": X, "chain_completeness": X, "no_hallucinated_links": X, "structural_awareness": X, "actionability": X, "total": X, "brief_comment": "..."}}"""


def evaluate_b(answer: str, gold: str) -> dict:
    prompt = EVAL_PROMPT_B.format(gold=gold, answer=answer)
    raw, _ = call_cerebras([{"role": "user", "content": prompt}], temperature=0.0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"hop_accuracy": 0, "chain_completeness": 0, "no_hallucinated_links": 0,
                "structural_awareness": 0, "actionability": 0, "total": 0,
                "brief_comment": f"Parse fail: {raw[:200]}"}


def run_part_b(approach: str, context: str, extra_meta: dict = None):
    system_msg = f"""You are an AI assistant helping with the Bean & Brew Go coffee shop project.

Here is the project context:

{context}

Answer questions about the project based ONLY on this context. Trace connections between layers, entities, and tests precisely."""

    results = []
    for s in GRAPH_SCENARIOS:
        print(f"  [{s['id']}] {s['name']}...", end="", flush=True)
        answer, latency = call_cerebras([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": s["prompt"]}
        ])
        scores = evaluate_b(answer, s["gold"])
        total = sum(scores.get(k, 0) for k in ["hop_accuracy", "chain_completeness",
                    "no_hallucinated_links", "structural_awareness", "actionability"])
        r = ScenarioResult(s["id"], s["name"], answer, latency, scores, total)
        results.append(r)
        print(f" {total}/25 ({latency}ms)")

    total_score = sum(r.total for r in results)
    data = {
        "approach": approach,
        "part": "B",
        "total_score": total_score,
        "max_score": 125,
        "percentage": round(total_score / 125 * 100, 1),
        "extra": extra_meta or {},
        "scenarios": [{"id": r.scenario_id, "name": r.scenario_name,
                       "total": r.total, "latency_ms": r.latency_ms,
                       "scores": r.scores} for r in results],
    }
    path = f"results_{approach}_part_b.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Part B: {total_score}/125 ({data['percentage']}%) → {path}")
    return data


if __name__ == "__main__":
    import sys
    approach = sys.argv[1] if len(sys.argv) > 1 else "test"
    context_file = sys.argv[2] if len(sys.argv) > 2 else "test_context.json"
    with open(context_file) as f:
        eps = json.load(f)
    ctx = "\n\n".join(f"### {e['name']}\n{e['content']}" for e in eps)
    print(f"\n🔬 Part B benchmark: {approach} ({len(ctx)} chars)\n")
    run_part_b(approach, ctx)
