"""Benchmark runner v2: separate generator/evaluator, multi-run with statistics.

Generator: Cerebras gpt-oss-120b (fast, generates answers)
Evaluator: Cerebras zai-glm-4.7 (reasoning model, evaluates with chain-of-thought)

Key improvements over v1:
- Separate LLM for generation and evaluation (eliminates circular bias)
- 3 runs with median, mean, stddev per scenario
- 1-4 scoring scale (research-backed, better discrimination)
- Evaluator reasoning chain logged for auditability
- Bias mitigation prompts in evaluation rubric
"""
from __future__ import annotations

import json
import math
import os
import statistics
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

SCENARIOS = [
    {
        "id": "S1",
        "name": "Генерация unit-теста",
        "prompt": "Напиши unit-тест для метода Order.CalculateTotal() с edge cases. Учти существующие тесты, не дублируй их.",
        "gold": "Тест покрывает: пустой список, один элемент, несколько элементов, большие числа, float precision. Не дублирует TestUnitOrderCalculateTotal и TestUnitOrderCalculateTotalEmpty."
    },
    {
        "id": "S2",
        "name": "Поиск покрытия endpoint",
        "prompt": "Какие тесты покрывают endpoint /api/v1/products? Перечисли все, включая косвенное покрытие.",
        "gold": "Direct API tests (28): TestAPIProductCRUD, TestAPIProductValidationError, TestAPIProductNotFound, TestAPIProductGetByID, TestAPIProductUpdate, TestAPIProductUpdateValidationError, TestAPIProductDelete, TestAPIProductDeleteNotFound, TestAPIProductSearch, TestAPIProductSearchEmpty, TestAPIProductSearchNoResults, TestAPIProductSearchWithLimit, TestAPIProductListPagination, TestAPIProductListByCategory, TestAPIProductInvalidJSON, TestAPIProductInvalidID, TestAPIProductCreateValidationCases (12 subtests), TestAPIProductUpdateInvalidID, TestAPIProductUpdateNotFound, TestAPIProductDeleteInvalidID, TestAPIProductListQueryParams (6 subtests), TestAPIProductListEmptyDB, TestAPIProductSearchQueryParams (5 subtests), TestAPIProductCRUDFullCycle, TestAPIProductCreateDuplicate. Indirect: TestIntegrationProduct* (26 tests), TestUnitProductUC* (25 tests)."
    },
    {
        "id": "S3",
        "name": "Анализ flaky-теста",
        "prompt": "Тест TestIntegrationProductSearch иногда падает. Найди возможные причины и предложи fix.",
        "gold": "Shared in-memory DB, зависимость от порядка записей, UTF-8/кириллица в LIKE, отсутствие изоляции между тестами. Fix: отдельная DB per test, t.Cleanup с truncate, или проверка TestIntegrationProductSearchUnicode."
    },
    {
        "id": "S4",
        "name": "Рефакторинг с обновлением тестов",
        "prompt": "Переименуй сущность NewsItem в Article — какие тесты и файлы нужно обновить? Перечисли ВСЕ.",
        "gold": "Files: entity/news.go, entity/news_test.go, entity/news_extended_test.go, usecase/news.go, usecase/usecase_test.go, usecase/news_uc_extended_test.go, repository/interfaces.go, repository/sqlite/news.go, repository/sqlite/news_test.go, repository/sqlite/news_extended_test.go, handler/news.go, handler/api_test.go, handler/news_api_extended_test.go, handler/pages.go, seed.go, migrations.go. Tests to rename (70+): TestUnitNewsItemValidate (10 subtests), TestUnitNewsItemSummary (6 subtests), TestUnitNewsItemSummaryEmptyContent/OneChar/MaxRunesZero/One/Two/Unicode, TestUnitNewsItemSummaryVariousLengths (15 subtests), TestUnitNewsItemSummaryMultibyteEdgeCases (8 subtests), TestUnitNewsItemValidateFieldCombinations (9 subtests), TestUnitNewsItemSummaryExactBoundary, TestUnitNewsItemSummaryNegativeMaxRunes, TestUnitNewsItemValidateContentPriorityOrder, TestAPINewsCRUD, TestAPINewsGetByID, TestAPINewsGetByIDNotFound, TestAPINewsUpdate, TestAPINewsUpdateValidation, TestAPINewsDelete, TestAPINewsDeleteNotFound, TestAPINewsValidationEmptyTitle/EmptyContent, TestAPINewsInvalidJSON, TestAPINewsListPagination, TestAPINewsCreateValidationCases (12 subtests), TestAPINewsUpdateInvalidID, TestAPINewsDeleteInvalidID, TestAPINewsGetInvalidID, TestAPINewsUpdateNotFound, TestAPINewsUpdateValidationCases (3 subtests), TestAPINewsListEmpty, TestAPINewsListPaginationEdgeCases (6 subtests), TestAPINewsCRUDFullCycle, TestAPINewsCreateWithAuthor, TestAPINewsDeleteAndVerifyList, TestAPINewsCreateMultipleAndCount, TestAPINewsUpdateAllFields, TestAPINewsListVerifiesTotal, TestIntegrationNews* (21 tests), TestUnitNewsUC* (24 tests)."
    },
    {
        "id": "S5",
        "name": "E2E тест для нового flow",
        "prompt": "Добавь тест для полного flow: создать категорию → добавить товар → оформить заказ → обработать → завершить. Покажи код.",
        "gold": "Тест использует httptest, вызывает POST /categories, POST /products, POST /orders, POST /orders/{id}/process, POST /orders/{id}/complete в правильной последовательности. Проверяет финальный статус completed и total."
    },
    {
        "id": "S6",
        "name": "Impact analysis изменения схемы",
        "prompt": "Если добавить поле weight float64 в таблицу products — какие тесты сломаются и какие файлы нужно изменить?",
        "gold": "Прямого падения не будет (поле nullable/default), но нужно обновить: entity/product.go (struct), repository/sqlite/product.go (scanProducts, Create, Update), migrations.go (ALTER TABLE). Тесты для обновления: все TestIntegrationProduct*, TestAPIProduct*, TestUnitProductValidate (если добавить валидацию weight)."
    },
    {
        "id": "S7",
        "name": "Обнаружение дублей",
        "prompt": "Есть ли дублирующиеся или пересекающиеся тесты в проекте? Перечисли все пары.",
        "gold": "TestUnitOrderCalculateTotal и TestUnitOrderCalculateTotalEmpty частично пересекаются (пустой список). TestIntegrationProductCRUD и TestAPIProductCRUD тестируют похожую логику на разных уровнях. TestUnitOrderCanCancel и TestUnitOrderCanCancelEdgeCases могут пересекаться. TestIntegrationOrderCancelFlow и TestAPIOrderCancel — разные уровни одного flow."
    },
    {
        "id": "S8",
        "name": "Генерация test plan",
        "prompt": "Мы добавляем систему скидок (купоны). Составь test plan по уровням тестирования.",
        "gold": "Unit: Coupon entity validation, ApplyDiscount с купонами, расчёт скидки. Integration: CouponRepository CRUD, применение купона к заказу в БД. API: POST/GET/DELETE /coupons, POST /orders с coupon_code. Usecase: CouponUseCase.Apply, валидация срока действия, лимит использований. E2E: создать купон → заказ со скидкой → проверить total."
    },
    {
        "id": "S9",
        "name": "Темпоральный контекст",
        "prompt": "Раньше тест TestUnitProductValidate проверял максимальную цену 100000. Почему это убрали?",
        "gold": "Агент должен честно сказать, что не имеет информации об истории изменений, или найти коммит. Не должен выдумывать причину."
    },
    {
        "id": "S10",
        "name": "Оптимизация тестового suite",
        "prompt": "Тестовый suite вырос до 600+ тестов. Что можно оптимизировать? Предложи конкретные действия с примерами.",
        "gold": "1) t.Parallel() для unit-тестов без shared state. 2) Общий testutil с setupTestDB. 3) Build tags для разделения unit/integration (go test -tags=integration). 4) Объединить мелкие table-driven тесты. 5) Кэширование DB setup между тестами одного пакета (TestMain). 6) Benchmark тесты для горячих путей."
    },
    {
        "id": "S11",
        "name": "Анализ тестового покрытия по слоям",
        "prompt": "Покажи матрицу покрытия: для каждой сущности (Product, Order, Category, NewsItem) — какие тесты есть на каждом слое (entity, repository, usecase, handler).",
        "gold": "Product: entity(Validate,ApplyDiscount,Boundary), repo(CRUD,List,Search,Count,Pagination,Unicode), usecase(Create,List,Search,Update,Delete), handler(CRUD,Validation,NotFound,Update,Delete,Search,Pagination). Order: entity(Validate,CalculateTotal,CanCancel,CanComplete,StatusTransitions,Boundary), repo(CRUD,StatusTransitions,ListByCustomer,Pagination,CancelFlow,CompleteFlow), usecase(Create,Cancel,Process,Complete), handler(Flow,Cancel,Process,Complete,NotFound,CustomerList). Category: entity(Validate,Boundary), repo(CRUD,GetBySlug,List,DuplicateSlug), usecase(CRUD,GetBySlug), handler(CRUD,Validation,Update,Delete). News: entity(Validate,Summary,Boundary), repo(CRUD,List,Count,Unicode), usecase(Pagination,CRUD,Count), handler(CRUD,Validation,Update,Delete,Pagination)."
    },
    {
        "id": "S12",
        "name": "Зависимости между тестами",
        "prompt": "Какие тесты зависят от setupTestDB? Что сломается если изменить схему миграций?",
        "gold": "Все Integration тесты зависят от setupTestDB (94 runs): TestIntegrationProduct* (26), TestIntegrationOrder* (17), TestIntegrationCategory* (18), TestIntegrationNews* (21). Все API тесты через setupTestServer (179 runs) — который внутри создаёт DB через sqliteRepo.Open + RunMigrations. Все Usecase тесты через setupUC (127 runs) — также создаёт DB. Итого: ~400 из 637 тестов зависят от миграций. Только 237 entity unit-тестов (TestUnitProduct*, TestUnitOrder*, TestUnitNewsItem*, TestUnitCategory*) не зависят от setupTestDB. При изменении миграций сломаются ~63% всех тестов."
    },
]

# Evaluation prompt with bias mitigation (research-backed)
EVAL_PROMPT_V2 = """You are an expert test engineering evaluator. Your job is to objectively assess an AI assistant's answer about a Go testing project.

IMPORTANT BIAS DISCLAIMERS:
- Do NOT prefer longer answers over shorter ones. Concise correct answers score the same as verbose correct ones.
- Score based on CONTENT, not on formatting or presentation style.
- If the answer partially matches the gold standard, give partial credit proportionally.

Score the ANSWER on 4 criteria using a 1-4 scale:
1 = Incorrect/Missing, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct

Criteria:
1. **Accuracy** (1-4): Are the facts correct? No made-up test names, files, or functions.
2. **Completeness** (1-4): Are ALL relevant items from the gold standard mentioned?
3. **Context Utilization** (1-4): Does the answer use real project context (not generic advice)?
4. **Actionability** (1-4): Can a developer act on this answer without additional research?

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


_http_client = httpx.Client(
    timeout=httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0),
    transport=httpx.HTTPTransport(retries=2),
)


def call_llm(messages: list[dict], model: str = GENERATOR_MODEL,
             temperature: float = 0.2, max_tokens: int = 2000) -> tuple[str, str, int]:
    """Call Cerebras LLM. Returns (content, reasoning, latency_ms)."""
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

    resp = _http_client.post(
        f"{CEREBRAS_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    latency = int((time.time() - t0) * 1000)
    msg = resp.json()["choices"][0]["message"]
    content = msg.get("content", "") or ""
    reasoning = msg.get("reasoning", "") or ""
    return content, reasoning, latency


def _extract_scores_json(text: str) -> dict | None:
    """Try to extract a JSON scores dict from text."""
    import re
    raw = text.strip()
    # Try ```json ... ``` blocks first
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        parts = raw.split("```")
        for part in parts[1::2]:  # odd indices = inside backticks
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if "{" in part:
                raw = part
                break

    keys = ["accuracy", "completeness", "context_utilization", "actionability"]
    try:
        scores = json.loads(raw)
        if isinstance(scores, dict) and any(k in scores for k in keys):
            scores["total"] = sum(scores.get(k, 0) for k in keys)
            return scores
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: find any JSON object with score keys
    for match in re.finditer(r'\{[^{}]+\}', text):
        try:
            candidate = json.loads(match.group())
            if isinstance(candidate, dict) and any(k in candidate for k in keys):
                candidate["total"] = sum(candidate.get(k, 0) for k in keys)
                return candidate
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def evaluate_v2(answer: str, gold: str) -> tuple[dict, str]:
    """Use GLM 4.7 (reasoning model) as judge. Returns (scores_dict, reasoning)."""
    prompt = EVAL_PROMPT_V2.format(gold=gold, answer=answer)
    content, reasoning, _ = call_llm(
        [{"role": "user", "content": prompt}],
        model=EVALUATOR_MODEL,
        temperature=0.0,
        max_tokens=8000,
    )

    keys = ["accuracy", "completeness", "context_utilization", "actionability"]

    # Try content first, then reasoning (GLM 4.7 may put JSON in either)
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


def run_single(approach: str, context_text: str, run_id: int) -> RunResult:
    """Run all scenarios once."""
    system_msg = (
        "You are an AI assistant helping with the Bean & Brew Go coffee shop project.\n\n"
        f"Here is the project context:\n\n{context_text}\n\n"
        "Answer questions about the project based ONLY on this context. "
        "Be specific: reference real test names, file paths, and function signatures."
    )

    results = []
    for s in SCENARIOS:
        print(f"  R{run_id} [{s['id']}] {s['name']}...", end="", flush=True)
        answer, _, latency = call_llm([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": s["prompt"]}
        ])
        scores, eval_reasoning = evaluate_v2(answer, s["gold"])
        total = scores.get("total", 0)
        r = ScenarioResult(
            scenario_id=s["id"],
            scenario_name=s["name"],
            answer=answer,
            latency_ms=latency,
            scores=scores,
            total=total,
            evaluator_reasoning=eval_reasoning[:500],  # truncate for storage
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
    """Compute per-scenario and overall statistics across runs."""
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
            "min": min(scores_per_run),
            "max": max(scores_per_run),
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


def save_results_v2(approach: str, runs: list[RunResult], stats: dict, extra: dict = None):
    """Save multi-run results with statistics."""
    max_per_scenario = 16  # 4 criteria × 4 max
    max_total = max_per_scenario * len(SCENARIOS)

    median_total = stats["overall"]["median"]
    data = {
        "version": "2.0",
        "approach": approach,
        "timestamp": datetime.now().isoformat(),
        "generator_model": GENERATOR_MODEL,
        "evaluator_model": EVALUATOR_MODEL,
        "num_runs": len(runs),
        "num_scenarios": len(SCENARIOS),
        "scoring": {"scale": "1-4", "criteria": 4, "max_per_scenario": max_per_scenario, "max_total": max_total},
        "statistics": stats,
        "median_total": median_total,
        "median_percentage": round(median_total / max_total * 100, 1),
        "extra": extra or {},
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

    path = f"results_v2_{approach}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*60}")
    print(f"Results saved to {path}")
    print(f"  Runs: {len(runs)}")
    print(f"  Median: {median_total}/{max_total} ({data['median_percentage']}%)")
    print(f"  Mean: {stats['overall']['mean']} ± {stats['overall']['stddev']}")
    print(f"  Range: {stats['overall']['min']} – {stats['overall']['max']}")
    return data


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python runner.py <approach> [context_file] [num_runs]")
        print("Approaches: md_files, github_issues, mem0, graphiti, helixir")
        print(f"Default: {NUM_RUNS} runs, GLM 4.7 evaluator")
        sys.exit(1)

    approach = sys.argv[1]
    context_file = sys.argv[2] if len(sys.argv) > 2 else "../shared/data/test_context.json"
    num_runs = int(sys.argv[3]) if len(sys.argv) > 3 else NUM_RUNS

    # Resolve context file path
    ctx_path = Path(context_file)
    if not ctx_path.exists():
        ctx_path = Path(__file__).parent / context_file
    if not ctx_path.exists():
        ctx_path = Path(__file__).parent.parent / "shared" / "data" / "test_context.json"

    with open(ctx_path) as f:
        episodes = json.load(f)
    context_text = "\n\n".join(f"### {ep['name']}\n{ep['content']}" for ep in episodes)

    print(f"\n{'='*60}")
    print(f"Benchmark v2: {approach}")
    print(f"  Context: {len(context_text):,} chars ({len(episodes)} episodes)")
    print(f"  Generator: {GENERATOR_MODEL}")
    print(f"  Evaluator: {EVALUATOR_MODEL}")
    print(f"  Runs: {num_runs}")
    print(f"  Scenarios: {len(SCENARIOS)}")
    print(f"  Scoring: 1-4 scale, 4 criteria, max {16 * len(SCENARIOS)}/run")
    print(f"{'='*60}\n")

    runs = []
    for i in range(1, num_runs + 1):
        print(f"\n--- Run {i}/{num_runs} ---")
        run = run_single(approach, context_text, i)
        runs.append(run)
        print(f"  Run {i} total: {run.total}/{16 * len(SCENARIOS)}")

    stats = compute_stats(runs)
    save_results_v2(approach, runs, stats)


if __name__ == "__main__":
    main()
