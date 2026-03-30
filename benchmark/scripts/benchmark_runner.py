"""Benchmark runner for AI context management approaches.

For each scenario, retrieves context from the approach's storage, sends it to
Cerebras LLM with the scenario question, evaluates the response, and records metrics.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime

import httpx

CEREBRAS_API_KEY = os.environ["CEREBRAS_API_KEY"]
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
CEREBRAS_MODEL = "gpt-oss-120b"

SCENARIOS = [
    {
        "id": "S1",
        "name": "Генерация unit-теста",
        "prompt": "Напиши unit-тест для метода Order.CalculateTotal() с edge cases. Учти существующие тесты, не дублируй их.",
        "gold": "Тест покрывает: пустой список, один элемент, несколько элементов, большие числа. Не дублирует TestUnitOrderCalculateTotal."
    },
    {
        "id": "S2",
        "name": "Поиск покрытия endpoint",
        "prompt": "Какие тесты покрывают endpoint /api/v1/products? Перечисли все.",
        "gold": "TestAPIProductCRUD, TestAPIProductValidationError, TestAPIProductNotFound, TestIntegrationProductCRUD, TestIntegrationProductList, TestIntegrationProductSearch, TestIntegrationProductCount"
    },
    {
        "id": "S3",
        "name": "Анализ flaky-теста",
        "prompt": "Тест TestIntegrationProductSearch иногда падает. Найди возможные причины.",
        "gold": "Shared in-memory DB, зависимость от порядка записей, UTF-8 в LIKE, отсутствие изоляции между тестами."
    },
    {
        "id": "S4",
        "name": "Рефакторинг с обновлением тестов",
        "prompt": "Переименуй сущность NewsItem в Article — какие тесты и файлы нужно обновить? Перечисли все.",
        "gold": "entity/news.go, entity/news_test.go, usecase/news.go, usecase/usecase_test.go, repository/interfaces.go, repository/sqlite/news.go, handler/news.go, handler/api_test.go, handler/pages.go, seed.go, migrations.go"
    },
    {
        "id": "S5",
        "name": "E2E тест для нового flow",
        "prompt": "Добавь тест для полного flow: создать категорию → добавить товар → оформить заказ → отменить заказ. Покажи код.",
        "gold": "Тест использует httptest, вызывает POST /categories, POST /products, POST /orders, POST /orders/{id}/cancel в правильной последовательности."
    },
    {
        "id": "S6",
        "name": "Impact analysis изменения схемы",
        "prompt": "Если добавить поле weight в таблицу products — какие тесты сломаются и какие файлы нужно изменить?",
        "gold": "Прямого падения не будет (поле nullable/default), но нужно обновить: scanProducts(), Create(), Update() в repository, и все тесты делающие Scan."
    },
    {
        "id": "S7",
        "name": "Обнаружение дублей",
        "prompt": "Есть ли дублирующиеся тесты в проекте? Перечисли пересекающиеся тесты.",
        "gold": "TestUnitOrderCalculateTotal и TestUnitOrderCalculateTotalEmpty частично пересекаются. TestIntegrationProductCRUD и TestAPIProductCRUD тестируют похожую логику на разных уровнях."
    },
    {
        "id": "S8",
        "name": "Генерация test plan",
        "prompt": "Мы добавляем систему скидок (купоны). Составь test plan по уровням тестирования.",
        "gold": "Plan включает: unit-тесты для Coupon entity validation, тест ApplyDiscount, integration-тест для CouponRepository, API-тесты для CRUD купонов, E2E-тест для заказа со скидкой."
    },
    {
        "id": "S9",
        "name": "Темпоральный контекст",
        "prompt": "Раньше тест TestUnitProductValidate проверял максимальную цену 100000. Почему это убрали?",
        "gold": "Агент должен честно сказать, что не имеет информации об истории изменений, или найти коммит."
    },
    {
        "id": "S10",
        "name": "Оптимизация тестового suite",
        "prompt": "Тестовый suite растёт. Что можно оптимизировать? Предложи конкретные действия.",
        "gold": "Объединить мелкие table-driven тесты, вынести setupTestDB в shared testutil, использовать t.Parallel() где нет shared state, выделить integration тесты в build tag."
    }
]

EVAL_PROMPT_TEMPLATE = """You are an expert evaluator. Score the ANSWER on 5 criteria (0-5 each):

1. **Accuracy**: Factual correctness
2. **Completeness**: Are all relevant tests/files/details mentioned?
3. **No Hallucination**: No made-up tests, files, functions
4. **Context Utilization**: Does it reference real project context (not guessing)?
5. **Actionability**: Can the answer be applied immediately without rework?

GOLD STANDARD ANSWER:
{gold}

ACTUAL ANSWER:
{answer}

Return JSON ONLY, no explanation:
{{"accuracy": X, "completeness": X, "no_hallucination": X, "context_utilization": X, "actionability": X, "total": X, "brief_comment": "..."}}"""


@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    answer: str = ""
    latency_ms: int = 0
    scores: dict = field(default_factory=dict)
    total: int = 0


_http_client = httpx.Client(
    timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0),
    transport=httpx.HTTPTransport(retries=2),
)


def call_cerebras(messages: list[dict], temperature: float = 0.2) -> tuple[str, int]:
    """Call Cerebras LLM, return (response_text, latency_ms)."""
    t0 = time.time()
    resp = _http_client.post(
        f"{CEREBRAS_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
        json={"model": CEREBRAS_MODEL, "messages": messages, "temperature": temperature, "max_tokens": 2000},
    )
    resp.raise_for_status()
    latency = int((time.time() - t0) * 1000)
    return resp.json()["choices"][0]["message"]["content"], latency


def evaluate(answer: str, gold: str) -> dict:
    """Use LLM-as-Judge to evaluate answer against gold standard."""
    prompt = EVAL_PROMPT_TEMPLATE.format(gold=gold, answer=answer)
    raw, _ = call_cerebras([{"role": "user", "content": prompt}], temperature=0.0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"accuracy": 0, "completeness": 0, "no_hallucination": 0, "context_utilization": 0, "actionability": 0, "total": 0, "brief_comment": f"Failed to parse: {raw[:200]}"}


def run_benchmark(approach_name: str, context_text: str) -> list[ScenarioResult]:
    """Run all 10 scenarios with the given context."""
    results = []
    system_msg = f"You are an AI assistant helping with the Bean & Brew Go coffee shop project.\n\nHere is the project context:\n\n{context_text}\n\nAnswer questions about the project based ONLY on this context."

    for s in SCENARIOS:
        print(f"  [{s['id']}] {s['name']}...", end="", flush=True)
        answer, latency = call_cerebras([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": s["prompt"]}
        ])
        scores = evaluate(answer, s["gold"])
        total = sum(scores.get(k, 0) for k in ["accuracy", "completeness", "no_hallucination", "context_utilization", "actionability"])
        r = ScenarioResult(
            scenario_id=s["id"],
            scenario_name=s["name"],
            answer=answer,
            latency_ms=latency,
            scores=scores,
            total=total,
        )
        results.append(r)
        print(f" {total}/25 ({latency}ms)")

    return results


def save_results(approach: str, results: list[ScenarioResult], extra_meta: dict = None):
    """Save results to JSON."""
    total = sum(r.total for r in results)
    data = {
        "approach": approach,
        "timestamp": datetime.now().isoformat(),
        "model": CEREBRAS_MODEL,
        "total_score": total,
        "max_score": 250,
        "percentage": round(total / 250 * 100, 1),
        "extra": extra_meta or {},
        "scenarios": [asdict(r) for r in results],
    }
    path = f"results_{approach}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Results saved to {path}: {total}/250 ({data['percentage']}%)")
    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python benchmark_runner.py <approach> [context_file]")
        print("Approaches: md_files, github_issues, mem0, graphiti, helixir")
        sys.exit(1)

    approach = sys.argv[1]
    context_file = sys.argv[2] if len(sys.argv) > 2 else "test_context.json"

    with open(context_file) as f:
        episodes = json.load(f)
    context_text = "\n\n".join(f"### {ep['name']}\n{ep['content']}" for ep in episodes)

    print(f"\n🔬 Running benchmark: {approach}")
    print(f"   Context: {len(context_text)} chars from {context_file}")
    print(f"   Model: {CEREBRAS_MODEL}\n")

    results = run_benchmark(approach, context_text)
    save_results(approach, results)
