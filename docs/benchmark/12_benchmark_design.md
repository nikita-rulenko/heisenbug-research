# Бенчмарк: управление тестовым контекстом AI-агентом

## Мотивация

Конференция Heisenbug ориентирована на тестировщиков. Мы исследуем, как разные подходы
к хранению контекста влияют на способность AI-агента работать с автотестами проекта.
Бенчмарк основан на реальном Go-проекте "Bean & Brew" (кофейный магазин) с 175 тестами (241 с подтестами)
четырёх уровней: entity unit (28 функций), repository integration (39), usecase (51), API handler (57).

## Методология

Вдохновлено:
- **LoCoMo** (Snap, ACL 2024) — бенчмарк долговременной памяти в диалогах, метрики F1/ROUGE/LLM-as-Judge
- **AgentBench** (2023) — многосредовая оценка AI-агентов
- **Galileo Agent Eval Framework** (2026) — rubric-based оценка с evidence-anchored scoring
- **arXiv:2601.20251** — FAQ method для статистической значимости LLM-бенчмарков

Наш бенчмарк адаптирует эти подходы к конкретной задаче: управление тестами через AI.

### v2 методология (улучшения)

Ключевые изменения в v2 по сравнению с v1:

1. **Раздельный генератор и оценщик** (eliminates circular evaluation bias):
   - Generator: `gpt-oss-120b` (Cerebras) — генерирует ответы
   - Evaluator: `zai-glm-4.7` (GLM 4.7 MoE, 358B total / 32B active) — оценивает с chain-of-thought
   - В v1 одна и та же модель генерировала и оценивала → переоценка собственных ответов

2. **Шкала 1-4 вместо 0-5** (research-backed):
   - 0 на шкале не несёт информации (отсутствие ответа)
   - 1-4 обеспечивает лучшую дискриминацию между уровнями качества
   - 4 критерия × 4 макс = 16 за сценарий, 12 сценариев × 16 = 192 макс

3. **3 прогона со статистикой**:
   - Каждый подход оценивается 3 раза
   - Рассчитываются median, mean, stddev для каждого сценария и overall
   - Медиана как финальный показатель (устойчива к выбросам LLM)

4. **Bias mitigation в промпте оценщика**:
   - Explicit disclaimers: не предпочитать длинные ответы, оценивать контент, не формат
   - Partial credit пропорционально корректным частям ответа

5. **Reasoning chain от оценщика**:
   - GLM 4.7 возвращает отдельное поле `reasoning` с цепочкой рассуждений
   - Логируется для аудита и воспроизводимости

6. **Расширенный контекст**: 21 эпизод, ~20K chars (vs 12 эпизодов, ~5.5K в v1)
   - 175 тестов создают реальную нагрузку на контекст
   - Достаточно для демонстрации деградации при росте тестовой базы

## 12 сценариев (Part A)

### S1: Генерация unit-теста
**Задача:** «Напиши unit-тест для метода `Order.CalculateTotal()` с edge cases»
**Что оцениваем:** Понимает ли агент контекст функции, видит ли существующие тесты, не дублирует ли их
**Золотой стандарт:** Тест покрывает: пустой список, один элемент, несколько элементов, большие числа. Не дублирует `TestUnitOrderCalculateTotal`.

### S2: Поиск покрытия endpoint
**Задача:** «Какие тесты покрывают endpoint `/api/v1/products`?»
**Что оцениваем:** Retrieval — находит ли агент все релевантные тесты (API + integration)
**Золотой стандарт:** Должен найти `TestAPIProductCRUD`, `TestAPIProductValidationError`, `TestAPIProductNotFound`, `TestIntegrationProductCRUD`, `TestIntegrationProductList`, `TestIntegrationProductSearch`, `TestIntegrationProductCount`.

### S3: Анализ flaky-теста
**Задача:** «Тест `TestIntegrationProductSearch` иногда падает. Найди возможные причины.»
**Что оцениваем:** Каузальный анализ — видит ли агент зависимости (shared DB state, порядок вставки, LIKE-запросы с кириллицей)
**Золотой стандарт:** Указание на: shared in-memory DB, зависимость от порядка записей, UTF-8 в LIKE, отсутствие изоляции между тестами.

### S4: Рефакторинг с обновлением тестов
**Задача:** «Переименуй сущность `NewsItem` в `Article` — какие тесты и файлы нужно обновить?»
**Что оцениваем:** Связность контекста — понимает ли агент все места использования
**Золотой стандарт:** entity/news.go, entity/news_test.go, usecase/news.go, usecase/usecase_test.go, repository/interfaces.go, repository/sqlite/news.go, handler/news.go, handler/api_test.go, handler/pages.go, seed.go, migrations.go.

### S5: E2E тест для нового flow
**Задача:** «Добавь тест для полного flow: создать категорию → добавить товар → оформить заказ → отменить заказ»
**Что оцениваем:** Знание существующих паттернов тестирования, API endpoints, зависимостей
**Золотой стандарт:** Тест использует httptest, вызывает POST /categories, POST /products, POST /orders, POST /orders/{id}/cancel в правильной последовательности.

### S6: Impact analysis изменения схемы
**Задача:** «Если добавить поле `weight` в таблицу `products` — какие тесты сломаются?»
**Что оцениваем:** Понимание связи schema ↔ repository ↔ тесты
**Золотой стандарт:** Прямого падения не будет (поле nullable/default), но нужно обновить: scanProducts(), Create(), Update() в repository, и все тесты делающие Scan.

### S7: Обнаружение дублей
**Задача:** «Есть ли дублирующиеся тесты в проекте?»
**Что оцениваем:** Целостная картина тестовой базы, умение видеть overlap
**Золотой стандарт:** TestUnitOrderCalculateTotal и TestUnitOrderCalculateTotalEmpty частично пересекаются (empty case). TestIntegrationProductCRUD и TestAPIProductCRUD тестируют похожую логику на разных уровнях (это нормально, но агент должен это заметить).

### S8: Генерация test plan для новой фичи
**Задача:** «Мы добавляем систему скидок (купоны). Составь test plan.»
**Что оцениваем:** Генерация на основе контекста проекта — использует ли существующие паттерны
**Золотой стандарт:** Plan включает: unit-тесты для Coupon entity validation, тест ApplyDiscount с купоном, integration-тест для CouponRepository, API-тесты для CRUD купонов, E2E-тест для заказа со скидкой.

### S9: Темпоральный контекст
**Задача:** «Раньше тест `TestUnitProductValidate` проверял максимальную цену 100000. Почему это убрали?»
**Что оцениваем:** Доступ к истории изменений, темпоральное рассуждение
**Золотой стандарт:** Агент должен честно сказать, что не имеет информации об истории изменений (если нет git/memory), или найти коммит (если есть).

### S10: Оптимизация тестового suite
**Задача:** «Тестовый suite вырос до 150+ тестов. Что можно оптимизировать? Предложи конкретные действия с примерами.»
**Что оцениваем:** Целостный анализ — видит ли агент паттерны, bottlenecks, redundancy
**Золотой стандарт:** 1) t.Parallel() для unit-тестов без shared state. 2) Общий testutil с setupTestDB. 3) Build tags для разделения unit/integration. 4) Объединить мелкие table-driven тесты. 5) Кэширование DB setup (TestMain). 6) Benchmark тесты для горячих путей.

### S11: Анализ тестового покрытия по слоям
**Задача:** «Покажи матрицу покрытия: для каждой сущности (Product, Order, Category, NewsItem) — какие тесты есть на каждом слое.»
**Что оцениваем:** Целостный retrieval через все 4 слоя × 4 сущности = 16 ячеек матрицы
**Золотой стандарт:** Product: entity(7 тестов), repo(14), usecase(13), handler(16). Order: entity(12), repo(4), usecase(19), handler(19). Category: entity(в news_test), repo(10), usecase(9), handler(10). News: entity(9), repo(11), usecase(10), handler(12).

### S12: Зависимости между тестами
**Задача:** «Какие тесты зависят от setupTestDB? Что сломается если изменить схему миграций?»
**Что оцениваем:** Понимание инфраструктурных зависимостей тестовой базы
**Золотой стандарт:** 147 из 175 тестов зависят от миграций (repo: 39, usecase: 51, handler: 57). Только 28 entity unit-тестов не зависят. При изменении миграций сломаются ~84% тестов.

## Критерии оценки Part A (v2)

| Критерий | Описание | Шкала |
|----------|----------|-------|
| **Accuracy** | Фактическая правильность: нет выдуманных тестов, файлов, функций | 1-4 |
| **Completeness** | Все ли релевантные элементы из gold standard упомянуты | 1-4 |
| **Context Utilization** | Использование реального контекста проекта, а не generic советов | 1-4 |
| **Actionability** | Можно ли разработчику действовать по ответу без дополнительного исследования | 1-4 |

**Максимум на сценарий:** 16 баллов (4 критерия × 4)
**Максимум Part A:** 192 балла (12 сценариев × 16)

> **Изменение vs v1**: объединили No Hallucination в Accuracy (галлюцинации = factual errors), убрали шкалу 0 (не несёт информации), перешли на 4 критерия × 1-4. Это даёт более чёткую дискриминацию.

## Дополнительные метрики (замеряем, но не скорим)

| Метрика | Как замеряем |
|---------|-------------|
| Latency | Время от запроса до полного ответа |
| Token usage | Объём токенов на запрос+ответ |
| Setup cost | Время и усилия на настройку подхода |
| Context rot | Деградация качества при повторных обращениях (серия из 10 запросов) |

## Метрики ресурсов (замеряем для каждого подхода)

| Метрика | Как замеряем |
|---------|-------------|
| RAM usage | `docker stats` — пиковое потребление памяти всех контейнеров подхода |
| Disk usage | `docker system df` / `du -sh` — объём образов + volumes |
| CPU usage | `docker stats` — средняя загрузка CPU за время бенчмарка |
| Container count | Количество контейнеров в стеке |
| Cold start time | Время от `docker compose up` до готовности принимать запросы |
| Dependencies | Количество внешних сервисов (DB, LLM, embeddings) |
| Setup wall time | Суммарное время от нуля до работающего стека (включая debugging) |
| Patches needed | Количество патчей/workaround поверх официальной документации |

## Часть B: Связность и скорость поиска (5 сценариев, graph-focused)

Эти сценарии целенаправленно проверяют способности, где графовые системы
должны превосходить плоский текст: multi-hop reasoning, causal chains, и retrieval quality.

### G1: Multi-hop dependency trace
**Задача:** «Покажи полную цепочку зависимостей от handler/order.go до entity/order.go через все слои. Какие тесты покрывают каждый слой?»
**Что оцениваем:** Способность проследить связи через 4 слоя архитектуры
**Золотой стандарт:** handler/order.go → OrderUsecase (usecase/order.go) → OrderRepository (repository/sqlite/order.go) → Order entity (entity/order.go). Тесты: TestAPIOrderFlow/Cancel/Complete → TestUsecaseOrderCreate/Cancel → TestIntegrationOrderCRUD/StatusUpdate/CancelFlow/CompleteFlow → TestUnitOrderCalculateTotal/CanCancel/CanComplete/Validate.

### G2: Cross-entity impact
**Задача:** «Если удалить поле CategoryID из Product — какие сущности, тесты и API endpoints это затронет? Проследи все связи.»
**Что оцениваем:** Граф-обход: Product → Category (FK) → API → tests
**Золотой стандарт:** entity/product.go (Validate ссылка на CategoryID), repository/sqlite/product.go (INSERT/UPDATE/Scan), handler/product.go (JSON parsing), TestUnitProductValidate, TestIntegrationProductCRUD, TestAPIProductCRUD, TestAPIOrderFlow (создаёт product с CategoryID), seed.go. Не затронет: news, order (кроме OrderFlow через product).

### G3: Causal chain (flaky → root cause → fix)
**Задача:** «TestIntegrationProductSearch flaky. Проследи: root cause → какие ещё тесты уязвимы к той же причине → как исправить системно.»
**Что оцениваем:** Рассуждение по цепочке: симптом → причина → распространение → решение
**Золотой стандарт:** Root cause: shared in-memory SQLite + LIKE с кириллицей. Уязвимы: все Integration тесты, использующие setupTestDB() без изоляции (TestIntegrationProductList, TestIntegrationOrderList). Системное решение: каждый тест — отдельная DB, или t.Cleanup с truncate, или build tag для изоляции.

### G4: Inverse lookup (test → what it validates)
**Задача:** «Для теста TestAPIOrderFlow — перечисли ВСЕ сущности, endpoints, бизнес-правила и helper-функции, которые он косвенно валидирует.»
**Что оцениваем:** Обратный обход: тест → слои → зависимости
**Золотой стандарт:** Entities: Category, Product, Order, OrderItem. Endpoints: POST /categories, POST /products, POST /orders. Бизнес-правила: Order.CalculateTotal (price*quantity), Product.Validate (required fields), Order.Validate (non-empty items). Helpers: setupTestServer, respondJSON, parseID. Косвенно: migrations.go (создание таблиц), seed.go (если используется).

### G5: Contradiction detection
**Задача:** «В проекте есть правило: тесты не должны зависеть от порядка выполнения. Найди все тесты, которые нарушают это правило.»
**Что оцениваем:** Обнаружение противоречий между правилами и реальностью
**Золотой стандарт:** TestIntegrationProductSearch (зависит от порядка INSERT), TestIntegrationSeedData (зависит от seed), TestAPIOrderFlow (зависит от последовательности POST-запросов — но это E2E, там допустимо). Usecase-тесты с real DB тоже потенциально зависят от порядка.

### Критерии оценки Части B

| Критерий | Описание | Шкала |
|----------|----------|-------|
| **Hop Accuracy** | Правильно ли прослежены связи между слоями/сущностями | 0-5 |
| **Chain Completeness** | Все ли звенья цепочки найдены | 0-5 |
| **No Hallucinated Links** | Нет ли выдуманных связей | 0-5 |
| **Structural Awareness** | Понимание архитектуры (слои, направления зависимостей) | 0-5 |
| **Actionability** | Можно ли по ответу действовать | 0-5 |

**Максимум на сценарий:** 25 баллов
**Максимум Часть B:** 125 баллов
**Максимум общий (A+B):** 375 баллов

### Метрика скорости поиска

Для систем с семантическим поиском (Mem0, Helixir) замеряем:

| Метрика | Как замеряем |
|---------|-------------|
| **p50 search latency** | Медиана времени вызова search по 15 запросам |
| **p95 search latency** | 95-й перцентиль |
| **Recall@5** | Из 5 top результатов — сколько релевантны (ручная проверка) |
| **Recall@10** | Из 10 top результатов |
| **Context precision** | Доля релевантного текста в возвращённом контексте (нет ли шума) |

Для систем без семантического поиска (MD, Issues) — N/A (весь контекст подаётся целиком).

## Часть C: Decision Reasoning (5 сценариев)

Части A и B проверяют **что** система знает. Часть C проверяет, хранит ли система
**почему** было принято решение: rationale, отвергнутые альтернативы, принятые trade-offs.

Это критично для долгоживущих проектов, где новые разработчики спрашивают
«а почему мы так сделали?» и агент должен восстановить цепочку рассуждений.

### D1: Архитектурное решение
**Решение:** Clean Architecture с 4 слоями
**Вопрос:** «Почему мы выбрали Clean Architecture? Какие альтернативы рассматривались?»
**Золотой стандарт:** 4-уровневая изоляция тестов. Плоская структура отвергнута (нельзя тестировать без DB). Trade-off: больше boilerplate, но 32 быстрых unit-теста.

### D2: Стратегия тестирования
**Решение:** Table-driven тесты с t.Run()
**Вопрос:** «Почему table-driven, а не отдельные функции?»
**Золотой стандарт:** Единая assertion point, лёгкое добавление subcases. Отдельные функции отвергнуты: дублирование setup. Пример: TestUnitProductValidate — 5 subcases в таблице.

### D3: Решение по flaky-тесту
**Решение:** Оставить TestIntegrationProductSearch despite flakiness
**Вопрос:** «Почему оставили flaky-тест? Какой trade-off?»
**Золотой стандарт:** ICU fix стоит +5MB binary + CGO + complex CI. Удаление отвергнуто — единственный тест на кириллицу. Trade-off: документированная flakiness.

### D4: Выбор технологии
**Решение:** SQLite вместо PostgreSQL
**Вопрос:** «Почему SQLite, не PostgreSQL? Какие недостатки приняли?»
**Золотой стандарт:** Single binary, in-memory тесты <1ms. PostgreSQL отвергнут: нужен Docker для тестов, overkill. Приняли: broken LIKE Unicode, no concurrent writes.

### D5: Подход к usecase-тестам
**Решение:** Real DB вместо моков в usecase-тестах
**Вопрос:** «Новый разработчик хочет моки. Какое было решение и почему?»
**Золотой стандарт:** Моки не ловят SQL-баги. In-memory SQLite так же быстр. 4 repos × 5 methods = 20 mock-методов — дорого. Trade-off: зависимость от SQLite, но ловим реальные баги.

### Критерии оценки Части C

| Критерий | Описание | Шкала |
|----------|----------|-------|
| **Rationale Recovery** | Содержит ли ответ исходное обоснование (не только факт решения) | 0-5 |
| **Alternatives Mentioned** | Названы ли отвергнутые альтернативы | 0-5 |
| **Trade-offs Articulated** | Упомянуты ли принятые недостатки/стоимость | 0-5 |
| **No Fabricated Reasoning** | Взято ли обоснование из контекста (не выдумано) | 0-5 |
| **Decision Traceability** | Можно ли проследить ответ до конкретной точки принятия решения | 0-5 |

**Максимум на сценарий:** 25 баллов
**Максимум Часть C:** 125 баллов
**Максимум общий (A+B+C):** 500 баллов

### Ключевое отличие от Частей A и B

Части A/B подают **одинаковый** контекст всем системам (test_context.json).
Часть C подаёт **дополнительные decision episodes** (decision_context.json) — 5 решений
с полным reasoning. Каждая система хранит их своим способом:
- MD/GH/Graphiti: как текст в контексте
- Mem0: через add_memory
- Helixir: через FastThink pipeline (think_start → think_add → think_conclude → think_commit)

Затем тестируем retrieval через `search_memory` / `search_reasoning_chain` / text search.

## Протокол проведения

1. Для каждого подхода создаём **чистую среду** (новый чат / новая сессия / чистая память)
2. Загружаем контекст проекта **один раз** через механизм подхода
3. Последовательно задаём 10 сценариев **в одной сессии**
4. Записываем ответы дословно
5. Оцениваем по критериям (LLM-as-Judge + ручная проверка)
6. Повторяем с шагами 1-5 **три раза** для статистической значимости
7. Берём **медиану** по трём прогонам

## Подходы для тестирования

| # | Подход | Механизм загрузки контекста |
|---|--------|-----------------------------|
| 1 | MD-файлы + .cursor/rules | Файлы в проекте, автоматически доступны агенту |
| 2 | GitHub Issues MCP | Issues с labels, milestone; запросы через MCP |
| 3 | Mem0 self-hosted | REST API, add + search memories |
| 4 | Graphiti | Python SDK, temporal knowledge graph |
| 5 | Helixir local | MCP server, add_memory + search_memory |

## Ссылки

- LoCoMo Benchmark: https://aclanthology.org/2024.acl-long.747.pdf
- Mem0 Research (LOCOMO results): https://mem0.ai/research
- AgentBench: https://github.com/THUDM/AgentBench
- Galileo Agent Eval Framework: https://galileo.ai/blog/agent-evaluation-framework-metrics-rubrics-benchmarks
- Evaluating AI Agents (practical guide): https://www.turingcollege.com/blog/evaluating-ai-agents-practical-guide
