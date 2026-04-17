# Как устроена оценка — шаг за шагом

> **Цель этого документа.** Честно показать, что именно получает LLM-генератор
> на вход, какие 22 задачи мы задаём, и по какому промту evaluator-LLM ставит
> баллы. Без этого любая таблица результатов — чёрный ящик.

## TL;DR — один прогон

1. Из `benchmarks/shared/data/test_context.json` собирается context_text (≈29KB).
2. Для каждой из 22 задач: генератор (`gpt-oss-120b`) получает
   `system = context_text + инструкция` + `user = prompt`, отдаёт ответ.
3. Evaluator (`zai-glm-4.7`) получает ответ + gold-standard + eval-промт,
   возвращает 4 балла (1–4 каждый).
4. Суммируем, берём медиану по 3 прогонам, считаем процент от 352.

Важно: в v2/v3 context_text **одинаковый для всех 5 подходов** — это
известное ограничение, разбор в [`03_phase4_plan.md`](03_phase4_plan.md#11-один-и-тот-же-контекст-для-всех-подходов).

---

## Модели и параметры

| Роль | Модель | Temperature | Источник |
|------|--------|:-----------:|----------|
| Generator | `gpt-oss-120b` | 0.2 | Cerebras |
| Evaluator | `zai-glm-4.7` | 0.0 | Cerebras |

Конфиг: `benchmarks/v2/runner.py:10-13` (`GENERATOR_MODEL`, `EVALUATOR_MODEL`).

Число прогонов: `NUM_RUNS = 3` (по каждому сценарию), берётся **медиана**.

---

## Part A — Facts & Retrieval (12 сценариев × max 16 = 192 балла)

Каждый сценарий — одна пара `prompt`/`gold`. Приведено **verbatim из кода**
(`benchmarks/v2/runner.py:34-107`).

### S1 — Генерация unit-теста

**Prompt.** Напиши unit-тест для метода `Order.CalculateTotal()` с edge cases.
Учти существующие тесты, не дублируй их.

**Gold.** Тест покрывает: пустой список, один элемент, несколько элементов,
большие числа, float precision. Не дублирует `TestUnitOrderCalculateTotal`
и `TestUnitOrderCalculateTotalEmpty`.

### S2 — Поиск покрытия endpoint

**Prompt.** Какие тесты покрывают endpoint `/api/v1/products`? Перечисли все,
включая косвенное покрытие.

**Gold.** 28 прямых API-тестов (`TestAPIProductCRUD`, `TestAPIProductValidationError`,
`TestAPIProductNotFound`, `TestAPIProductGetByID`, `TestAPIProductUpdate`,
`TestAPIProductUpdateValidationError`, `TestAPIProductDelete`, `TestAPIProductDeleteNotFound`,
`TestAPIProductSearch`, `TestAPIProductSearchEmpty`, `TestAPIProductSearchNoResults`,
`TestAPIProductSearchWithLimit`, `TestAPIProductListPagination`, `TestAPIProductListByCategory`,
`TestAPIProductInvalidJSON`, `TestAPIProductInvalidID`, `TestAPIProductCreateValidationCases`
(12 subtests), `TestAPIProductUpdateInvalidID`, `TestAPIProductUpdateNotFound`,
`TestAPIProductDeleteInvalidID`, `TestAPIProductListQueryParams` (6 subtests),
`TestAPIProductListEmptyDB`, `TestAPIProductSearchQueryParams` (5 subtests),
`TestAPIProductCRUDFullCycle`, `TestAPIProductCreateDuplicate`). Indirect:
`TestIntegrationProduct*` (26), `TestUnitProductUC*` (25).

### S3 — Анализ flaky-теста

**Prompt.** Тест `TestIntegrationProductSearch` иногда падает. Найди возможные
причины и предложи fix.

**Gold.** Shared in-memory DB, зависимость от порядка записей, UTF-8/кириллица
в LIKE, отсутствие изоляции между тестами. Fix: отдельная DB per test,
`t.Cleanup` с truncate, или проверка `TestIntegrationProductSearchUnicode`.

### S4 — Рефакторинг с обновлением тестов

**Prompt.** Переименуй сущность `NewsItem` в `Article` — какие тесты и файлы
нужно обновить? Перечисли ВСЕ.

**Gold.** 16 файлов (`entity/news.go`, `entity/news_test.go`, `entity/news_extended_test.go`,
`usecase/news.go`, `usecase/usecase_test.go`, `usecase/news_uc_extended_test.go`,
`repository/interfaces.go`, `repository/sqlite/news.go`, `repository/sqlite/news_test.go`,
`repository/sqlite/news_extended_test.go`, `handler/news.go`, `handler/api_test.go`,
`handler/news_api_extended_test.go`, `handler/pages.go`, `seed.go`, `migrations.go`)
+ 70+ тестов для переименования. Полный список — в коде gold.

### S5 — E2E тест для нового flow

**Prompt.** Добавь тест для полного flow: создать категорию → добавить товар →
оформить заказ → обработать → завершить. Покажи код.

**Gold.** Тест использует `httptest`, вызывает `POST /categories`, `POST /products`,
`POST /orders`, `POST /orders/{id}/process`, `POST /orders/{id}/complete`
в правильной последовательности. Проверяет финальный статус `completed` и `total`.

### S6 — Impact analysis изменения схемы

**Prompt.** Если добавить поле `weight float64` в таблицу `products` — какие
тесты сломаются и какие файлы нужно изменить?

**Gold.** Прямого падения не будет (поле nullable/default), но нужно обновить:
`entity/product.go` (struct), `repository/sqlite/product.go` (`scanProducts`, `Create`, `Update`),
`migrations.go` (`ALTER TABLE`). Тесты: все `TestIntegrationProduct*`,
`TestAPIProduct*`, `TestUnitProductValidate`.

### S7 — Обнаружение дублей

**Prompt.** Есть ли дублирующиеся или пересекающиеся тесты в проекте?
Перечисли все пары.

**Gold.** `TestUnitOrderCalculateTotal` ↔ `TestUnitOrderCalculateTotalEmpty`,
`TestIntegrationProductCRUD` ↔ `TestAPIProductCRUD`,
`TestUnitOrderCanCancel` ↔ `TestUnitOrderCanCancelEdgeCases`,
`TestIntegrationOrderCancelFlow` ↔ `TestAPIOrderCancel`.

### S8 — Генерация test plan

**Prompt.** Мы добавляем систему скидок (купоны). Составь test plan по уровням
тестирования.

**Gold.** Unit: `Coupon` entity validation, `ApplyDiscount` с купонами, расчёт
скидки. Integration: `CouponRepository` CRUD, применение купона к заказу в БД.
API: `POST/GET/DELETE /coupons`, `POST /orders` с `coupon_code`. Usecase:
`CouponUseCase.Apply`, валидация срока действия, лимит использований.
E2E: создать купон → заказ со скидкой → проверить `total`.

### S9 — Темпоральный контекст

**Prompt.** Раньше тест `TestUnitProductValidate` проверял максимальную цену
`100000`. Почему это убрали?

**Gold.** Агент должен **честно сказать**, что не имеет информации об истории
изменений, или найти коммит. **Не должен выдумывать причину.**

### S10 — Оптимизация тестового suite

**Prompt.** Тестовый suite вырос до 600+ тестов. Что можно оптимизировать?
Предложи конкретные действия с примерами.

**Gold.** 1) `t.Parallel()` для unit-тестов без shared state. 2) Общий testutil
с `setupTestDB`. 3) Build tags для разделения unit/integration. 4) Объединить
мелкие table-driven тесты. 5) Кэширование DB setup через `TestMain`.
6) Benchmark тесты для горячих путей.

### S11 — Матрица покрытия по слоям

**Prompt.** Покажи матрицу покрытия: для каждой сущности (Product, Order,
Category, NewsItem) — какие тесты есть на каждом слое (entity, repository,
usecase, handler).

**Gold.** Полная матрица 4 сущности × 4 слоя с конкретными именами тестов
на каждой ячейке — см. код.

### S12 — Зависимости между тестами

**Prompt.** Какие тесты зависят от `setupTestDB`? Что сломается если изменить
схему миграций?

**Gold.** Все Integration (94 runs), все API через `setupTestServer` (179 runs),
все Usecase через `setupUC` (127 runs). Итого: ~400 из 637 тестов. Только 237
entity unit-тестов не зависят от `setupTestDB`. При изменении миграций
сломаются ~63% всех тестов.

---

## Part B — Graph reasoning (5 сценариев × max 16 = 80 баллов)

Проверяет способность проследить **связи**, а не просто вспомнить факт.
Verbatim из `benchmarks/v2/part_b.py:24-55`.

### G1 — Multi-hop dependency trace

**Prompt.** Покажи полную цепочку зависимостей от `handler/order.go` до
`entity/order.go` через все слои. Какие тесты покрывают каждый слой?

**Gold.** `handler/order.go → OrderUsecase (usecase/order.go) → OrderRepository
(repository/sqlite/order.go) → Order entity (entity/order.go)`. Тесты
на каждом слое с конкретными именами.

### G2 — Cross-entity impact

**Prompt.** Если удалить поле `CategoryID` из `Product` — какие сущности,
тесты и API endpoints это затронет? Проследи все связи.

**Gold.** `entity/product.go`, `repository/sqlite/product.go`, `handler/product.go`,
`TestUnitProductValidate`, `TestIntegrationProductCRUD`, `TestAPIProductCRUD`,
`TestAPIOrderFlow` (создаёт product с `CategoryID`), `seed.go`.
Не затронуты: news, order (кроме OrderFlow).

### G3 — Causal chain: flaky → root cause → fix

**Prompt.** `TestIntegrationProductSearch` flaky. Проследи цепочку: root cause
→ какие ещё тесты уязвимы к той же причине → как исправить системно.

**Gold.** Root cause: shared in-memory SQLite + LIKE с кириллицей.
Vulnerable: все Integration с `setupTestDB()` без изоляции.
Fix: отдельная DB per test, или `t.Cleanup` с truncate, или build tag.

### G4 — Inverse lookup: test → what it validates

**Prompt.** Для теста `TestAPIOrderFlow` — перечисли ВСЕ сущности, endpoints,
бизнес-правила и helper-функции, которые он косвенно валидирует.

**Gold.** Entities: Category, Product, Order, OrderItem. Endpoints: `POST /categories`,
`POST /products`, `POST /orders`. Business rules: `Order.CalculateTotal`,
`Product.Validate`, `Order.Validate`. Helpers: `setupTestServer`, `respondJSON`,
`parseID`. Indirect: `migrations.go`, `seed.go`.

### G5 — Contradiction detection

**Prompt.** В проекте есть правило: тесты не должны зависеть от порядка
выполнения. Найди все тесты, которые нарушают это правило.

**Gold.** `TestIntegrationProductSearch` (INSERT order), `TestIntegrationSeedData`
(seed), `TestAPIOrderFlow` (sequential POST — но E2E, допустимо). Usecase
тесты с реальной DB потенциально зависят от порядка.

---

## Part C — Decision reasoning (5 сценариев × max 16 = 80 баллов)

Проверяет способность вспомнить **ПОЧЕМУ**, а не только **ЧТО**. Verbatim из
`benchmarks/shared/data/decision_context.json`.

### D1 — Почему Clean Architecture?

**Question.** Почему мы выбрали Clean Architecture? Какие альтернативы
рассматривались и почему были отвергнуты?

**Gold.** 4-level test isolation (entity без DB, usecase может мокать repo,
integration hits real SQLite, API через `httptest`). Flat structure отвергнута:
нельзя тестировать бизнес-логику без DB, рефакторинг ломает тесты, flaky
распространяются. Trade-off: больше boilerplate ради 32 быстрых unit-тестов.

### D2 — Почему table-driven тесты?

**Question.** Почему мы используем table-driven тесты вместо отдельных
тестовых функций? В чём обоснование?

**Gold.** Единая точка assertion (one fix for API change), легко добавить
subcase, понятные имена через `t.Run()`. Отдельные функции отвергнуты:
дублирование setup, взрывной рост функций.

### D3 — Почему flaky-тест оставили в suite?

**Question.** Почему `TestIntegrationProductSearch` оставили в suite несмотря
на flaky-статус? Какой trade-off был принят?

**Gold.** Исправление требует ICU extension (+5MB бинарника, `CGO_ENABLED=1`,
сложный CI). Cost > benefit — тест проходит 9 из 10 раз. Удаление отвергнуто:
он единственный проверяет поиск по кириллице.

### D4 — Почему SQLite, а не PostgreSQL?

**Question.** Почему выбрали SQLite, а не PostgreSQL? Какие недостатки приняли?

**Gold.** Single binary (нет DB-сервера), in-memory тесты (<1ms setup, без
Docker), маленький проект. Postgres отвергнут: нужен Docker для тестов,
сложный CI, overkill. Принятые недостатки: сломанный LIKE с Unicode
(причина flaky), нет concurrent writes, лимит размера DB.

### D5 — Почему real DB в usecase-тестах, а не моки?

**Question.** Новый разработчик предлагает: "Давайте в usecase-тестах
используем моки вместо реальной DB." Какое было исходное решение и почему?

**Gold.** Real DB потому что: 1) моки не ловят SQL-баги; 2) in-memory SQLite
так же быстр как мок; 3) usecase — тонкий слой, моки бы дублировали
integration-тесты. `gomock`/`testify` отвергнуты: 4 repo × 5 методов = 20
mock-методов, дорого в поддержке. Trade-off: usecase зависит от SQLite,
но ловит реальные SQL-баги.

---

## Eval-промт (verbatim)

### Part A — `EVAL_PROMPT_V2`

Источник: `benchmarks/v2/runner.py:110-136`.

```text
You are an expert test engineering evaluator. Your job is to objectively
assess an AI assistant's answer about a Go testing project.

IMPORTANT BIAS DISCLAIMERS:
- Do NOT prefer longer answers over shorter ones. Concise correct answers
  score the same as verbose correct ones.
- Score based on CONTENT, not on formatting or presentation style.
- If the answer partially matches the gold standard, give partial credit
  proportionally.

Score the ANSWER on 4 criteria using a 1-4 scale:
1 = Incorrect/Missing, 2 = Partially correct, 3 = Mostly correct, 4 = Fully correct

Criteria:
1. **Accuracy** (1-4): Are the facts correct? No made-up test names, files,
   or functions.
2. **Completeness** (1-4): Are ALL relevant items from the gold standard
   mentioned?
3. **Context Utilization** (1-4): Does the answer use real project context
   (not generic advice)?
4. **Actionability** (1-4): Can a developer act on this answer without
   additional research?

GOLD STANDARD (reference answer):
{gold}

ANSWER TO EVALUATE:
{answer}

First reason step-by-step about each criterion, then return your final scores.
You MUST end your response with a JSON block (and nothing after it):
```json
{"accuracy": X, "completeness": X, "context_utilization": X, "actionability": X,
 "total": X, "reasoning_summary": "..."}
```
```

### Part B — `EVAL_PROMPT_B_V2`

Тот же skeleton, но **критерии адаптированы под graph reasoning**
(`benchmarks/v2/part_b.py:57-83`):

```text
1. **Accuracy** (1-4): Are the connections/chains traced correctly? No made-up links.
2. **Completeness** (1-4): Are ALL links in the chain found? All affected items listed?
3. **Context Utilization** (1-4): Does the answer use real project context?
4. **Actionability** (1-4): Can a developer act on this answer to trace/fix?
```

### Part C — `EVAL_PROMPT_C_V2`

Источник: `benchmarks/v2/part_c.py:34-67`. Критерии про rationale:

```text
1. **Accuracy** (1-4): Is the rationale correct? Does it match the actual
   reasoning, not hallucinated?
2. **Completeness** (1-4): Are ALL key points covered — alternatives,
   trade-offs, reasoning chain?
3. **Context Utilization** (1-4): Does the answer reference real project
   specifics (not generic advice)?
4. **Actionability** (1-4): Can someone use this answer to understand and
   defend the decision?
```

---

## Что получает генератор на вход

Одним блоком (упрощённо):

```text
system: You are an AI assistant helping with the Bean & Brew Go coffee shop project.

        Here is the project context:
        ### episode 1 title
        episode 1 content...

        ### episode 2 title
        ...

        Answer the user's question based on this context.

user:   <prompt из сценария>
```

`context_text` — это склейка всех episodes из `benchmarks/shared/data/test_context.json`.
В v2/v3 этот текст **одинаковый для всех 5 подходов** (`md_files`, `github_issues`,
`mem0`, `graphiti`, `helixir`). Это не имитация настоящего retrieval — это
сводный «идеальный» контекст. Честный per-approach retrieval есть только в
[Context Recovery benchmark](../results/context_recovery.md) и будет в [v4
task-spec benchmark](04_v4_taskspec_design.md).

---

## Что получает evaluator

Отдельный HTTP-вызов. Ответ генератора и gold подставляются в eval-промт:

```text
<eval prompt выше>

GOLD STANDARD (reference answer):
<текст gold из сценария>

ANSWER TO EVALUATE:
<ответ генератора>
```

Temperature evaluator-а — `0.0` (детерминизм). Модель — `zai-glm-4.7`.
Ответ парсится регуляркой: ищется последний JSON-блок, достаются 4 балла.
Если парсинг упал — скоры `0`, причина сохраняется в `reasoning_summary`.

---

## Агрегация

1. **На задачу за прогон** — сумма 4 критериев = `total` (0–16).
2. **На задачу через 3 прогона** — **медиана** трёх `total` (устойчивее
   к выбросам, чем среднее).
3. **На подход** — сумма медиан по всем 22 задачам, max 352.
4. **Проценты** — `sum / 352 * 100`.

Три прогона — минимум; для статистической значимости нужно 10+. Это
зафиксировано как ограничение в [`01_design.md`](01_design.md) и как задача
в [`03_phase4_plan.md`](03_phase4_plan.md).

---

## Где лежит код

- `benchmarks/v2/runner.py` — SCENARIOS (Part A) + EVAL_PROMPT_V2 + call_llm
- `benchmarks/v2/part_b.py` — GRAPH_SCENARIOS + EVAL_PROMPT_B_V2
- `benchmarks/v2/part_c.py` — EVAL_PROMPT_C_V2 (DECISIONS берутся из JSON)
- `benchmarks/shared/data/test_context.json` — episodes для context_text
- `benchmarks/shared/data/decision_context.json` — 5 decisions для Part C
- `benchmarks/v2/helixir_mcp.py` — обёртка для helixir через MCP
  (остальные 4 подхода получают одинаковый context_text)

## Известные ограничения этой оценки

См. [`03_phase4_plan.md`](03_phase4_plan.md). Если коротко:

- Один context_text на все подходы → v2/v3 измеряют шум LLM, не retrieval.
- Golds с длинными перечислениями наказывают фильтрацию.
- Part C — recall правильного абзаца, не reasoning.
- 3 прогона — не статистика.
- Нет floor/ceiling baselines (пустой контекст, полный AGENTS.md).

v4 task-spec benchmark — попытка закрыть первые два пункта —
описан в [`04_v4_taskspec_design.md`](04_v4_taskspec_design.md).
