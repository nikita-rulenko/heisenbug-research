# Heisenbug 2026 — Исследование подходов к управлению контекстом AI-агентов

> Материалы к докладу на [Heisenbug 2026](https://heisenbug.ru/talks/8f09764b2d54406981d189ceb30ef032/)

## О чём исследование

При работе с AI-агентами (Cursor, Copilot, Cline) ключевая проблема — **деградация контекста**:
агент забывает архитектурные решения, дублирует тесты, путает слои приложения.

Мы **практически** сравнили 5 подходов к хранению и управлению контекстом
на примере Go-портала на 4 уровнях: Unit, Integration, API, UseCase.

### Как читать результаты

Мы задаём AI-агенту **22 задачи** по тестированию реального Go-проекта (637 тестов, 4 слоя архитектуры). Задачи разделены на три части:

| Часть | Что проверяет | Пример задачи | Сценариев | Max баллов |
|-------|--------------|---------------|:---------:|:----------:|
| **Part A** | Факты и retrieval | «Какие тесты покрывают `/api/v1/products`?» | 12 | 192 |
| **Part B** | Граф-рассуждения | «Проследи цепочку зависимостей handler → entity» | 5 | 80 |
| **Part C** | Decision reasoning | «Почему выбрали SQLite, а не PostgreSQL?» | 5 | 80 |
| | | **Итого** | **22** | **352** |

Каждый ответ оценивает **отдельная LLM-модель** (не та, что отвечала) по 4 критериям: accuracy, completeness, context utilization, actionability. Шкала 1-4 на критерий, **max 16 баллов за задачу**. Три прогона, берём медиану. Процент = доля от максимума 352. [**Как и почему мы сделали бенчмарк именно таким** →](docs/benchmark/12_benchmark_design.md) (эволюция v0→v2, все 22 сценария с обоснованиями, ограничения)

---

### Benchmark v3 — Масштабный тест: 637 тестов

> Проект масштабирован с 175 до **637 тестов** (29KB контекст). Mem0 и Helixir хранят устаревшие данные.

| # | Подход | v2 (175 тестов) | v3 (637 тестов) | Delta |
|---|--------|:--------------:|:--------------:|:-----:|
| 1 | **GitHub Issues** MCP | 262 (74.4%) | **267 (75.9%)** | **+1.4%** |
| 2 | **Graphiti** (raw fallback) | 248 (70.5%) | **261 (74.1%)** | **+3.7%** |
| 3 | **Mem0** (self-hosted) | **266 (75.6%)** | 260 (73.9%) | -1.7% |
| 4 | **MD-файлы** (.cursor/rules) | 265 (75.3%) | 256 (72.7%) | -2.6% |
| 5 | **Helixir MCP** (full tools) | 265 (75.3%) | 255 (72.4%) | **-2.8%** |

> 💡 Например: GitHub Issues набрал 267 из 352 возможных баллов = 75.9%. Это значит, что агент с контекстом из GitHub Issues в среднем выдаёт ответы на ¾ от идеала по всем 22 задачам.

### Context Recovery Benchmark — стоимость онбординга

Отдельный бенчмарк: сколько **токенов и денег** тратит агент, чтобы "вспомнить" проект через каждый источник контекста. Двухфазный: сначала загрузка контекста, затем 5 проверочных вопросов. Accuracy = доля правильных ответов на проверочные вопросы.

> **Главная находка v3**: семантическая память требует обслуживания. Устаревшие данные = потеря accuracy.

| Подход | Accuracy | Токены | Стоимость | CPR |
|--------|:--------:|-------:|----------:|----:|
| **MD files** | **88.8%** | 53,195 | $0.032 | 2,225 |
| **GitHub Issues** | **88.8%** | 54,397 | $0.033 | 2,175 |
| **Graphiti** | **88.8%** | 53,402 | $0.032 | 2,216 |
| **Helixir MCP** | 75.0% | 170,668 | $0.102 | 586 |
| **Mem0** | 58.8% | 29,638 | $0.018 | 2,643 |

> 💡 **Токены** = объём текста, который LLM прочитала и сгенерировала. **Стоимость** = цена в долларах по [тарифу Cerebras](#методология-расчёта-стоимости). **CPR** (Cost-Performance Ratio) = качество за доллар, чем выше — тем эффективнее. [Методология расчёта →](#методология-расчёта-стоимости)

**Mem0**: accuracy drop **-30pp** (88.8% → 58.8%) — хранит устаревшие "62 теста" вместо 637.
**Helixir**: потратил **3.2x больше** ($0.102 vs $0.032) токенов, но восстановил только 75%.
**MD/Issues/Graphiti**: получают актуальный контекст напрямую — 88.8% accuracy.

### Разбивка v3 по типам задач

| Подход | Part A — факты (192) | Part B — граф (80) | Part C — решения (80) | Total |
|--------|:-------------------:|:-----------------:|:--------------------:|:-----:|
| **GitHub Issues** | 135 (70.3%) | 57 (71.2%) | 75 (93.8%) | **267** |
| **Graphiti** | 135 (70.3%) | 51 (63.7%) | 75 (93.8%) | **261** |
| **Mem0** | 126 (65.6%) | 55 (68.8%) | 79 (98.8%) | **260** |
| **MD files** | 121 (63.0%) | 59 (73.8%) | 76 (95.0%) | **256** |
| **Helixir MCP** | 115 (59.9%) | 61 (76.2%) | 79 (98.8%) | **255** |

### Какой подход лучше для какого типа задач

| Тип задачи | Лидер v3 | Почему | Стоимость (онбординг) |
|------------|---------|--------|----------------------|
| **Фактуальные вопросы** (Part A) | GitHub Issues, Graphiti (70.3%) | Структурированный формат (заголовок+body, nodes) лучше индексирует большие объёмы | $0.033 / $0.032 |
| **Граф-рассуждения** (Part B) | Helixir MCP (76.2%) | Каузальные цепочки (IMPLIES/BECAUSE) — прямое преимущество для multi-hop trace | $0.102 |
| **Decision reasoning** (Part C) | Mem0, Helixir (98.8%) | Семантическая память отлично хранит стабильные решения ("почему SQLite?") | $0.018 / $0.102 |
| **Онбординг (Context Recovery)** | MD files (88.8%, $0.032) | Прямой доступ к актуальному тексту, нет stale данных, минимальная стоимость | $0.032 |
| **Cost-efficiency (CPR)** | Mem0 (2,643 quality/cost) | Минимальные токены (29K), но **только если данные актуальны** — иначе 58.8% | $0.018 |
| **Устаревший контекст** | MD files / GitHub Issues | Обновляются перезаписью файла (бесплатно). Mem0/Helixir требуют переиндексации | $0.032-$0.033 |

> **Главный инсайт**: нет одного лучшего подхода. Helixir лидирует в граф-рассуждениях (Part B: 76.2%) и decision reasoning (Part C: 98.8%), но проигрывает на фактуальных вопросах (Part A: 59.9%) из-за устаревших данных с высоким confidence (0.83). GitHub Issues — лучший баланс accuracy/стоимость при актуальном контексте.

### Ключевые выводы v2+v3

1. **На масштабе <50KB контекста (637 тестов, 29KB) подходы выравниваются** (72-76%). Различия в 3.5pp статистически незначимы при stddev 7-15.

2. **Семантическая память (Mem0, Helixir) требует обслуживания**. Устаревший контекст = деградация accuracy до 58-75%. Это OPEX, невидимый при первоначальной оценке.

3. **MD-файлы обновляются бесплатно** (перезапись файла). Mem0/Helixir требуют переиндексации (~30+ API calls к embedding).

4. **GitHub Issues показали рост** (+1.4%) — формат "заголовок + body" лучше структурирует большие объёмы.

5. **Для реального расхождения** нужен контекст 200K+ chars (~50K+ tokens) — чтобы не помещался в context window.

| Масштаб | Контекст | Рекомендация |
|---------|----------|-------------|
| **< 50KB** (~12K tok) | Всё в окне | MD files (бесплатно, просто) |
| **50-200KB** | На грани | GitHub Issues + поиск |
| **200-500KB** | Не влезает | Mem0 / Helixir (если обновлены!) |
| **>500KB** | Enterprise | Graphiti / Helixir (каузальный граф) |

[Подробный анализ v3](docs/benchmark/20_benchmark_v3_results.md)

<details>
<summary>Benchmark v2 — базовая таблица (175 тестов)</summary>

> Generator: gpt-oss-120b -> Evaluator: zai-glm-4.7 | Шкала 1-4 | 3 прогона, медиана

| # | Подход | Part A (192) | Part B (80) | Part C (80) | **Итого** | **%** |
|---|--------|:------------:|:-----------:|:-----------:|:---------:|:-----:|
| 1 | **Mem0** | 125 | 62 | 79 | **266** | **75.6%** |
| 2 | **Helixir MCP** | 124 | 63 | 78 | **265** | **75.3%** |
| 2 | **MD-файлы** | 123 | 62 | 80 | **265** | **75.3%** |
| 4 | **GitHub Issues** | 122 | 60 | 80 | **262** | **74.4%** |
| 5 | **Graphiti** | 107 | 63 | 78 | **248** | **70.5%** |

</details>

### Context Recovery Benchmark (демо для конференции)

Бенчмарк онбординга — [дизайн и методология](docs/benchmark/19_context_recovery_benchmark.md). Для live-демо на конференции: split-screen с token-счётчиками.

## Структура репозитория

```
heisenbug-research/
├── docs/                          # Документация исследования
│   ├── background/                #   Обзор литературы и анализ фреймворков
│   ├── experiments/               #   Описание каждого эксперимента
│   ├── benchmark/                 #   Дизайн, результаты, context recovery
│   └── notes/                     #   Рабочие заметки
│
├── benchmark/                     # Код бенчмарка
│   ├── scripts/                   #   Python-скрипты (v2 runner, part_b, part_c, helixir_mcp, context_recovery)
│   ├── data/                      #   Контекстные данные (29 эпизодов, 5 решений)
│   └── results/                   #   JSON-результаты v2 + v3 (36 файлов)
│
├── infra/                         # Инфраструктура
│   ├── mem0/                      #   Docker + patched FastAPI server
│   ├── graphiti/                  #   FalkorDB + graphiti-core SDK
│   ├── helixir-local/             #   HelixDB + helix.toml
│   └── mcp/                       #   MCP-серверы (mem0_mcp_server.py)
│
├── scripts/                       # Утилиты
│   ├── dashboard_recovery.html    #   Веб-дашборд для конференции (live demo)
│   ├── demo_live.sh               #   Скрипт живого демо
│   ├── generate_pptx.py           #   Генерация слайдов
│   └── render_*.py                #   Рендеринг таблиц (PNG)
│
├── assets/                        # Визуальные материалы
│   ├── diagrams/                  #   D2-диаграммы (src + rendered SVG/PNG)
│   └── tables/                    #   Сравнительные таблицы (PNG)
│
└── presentation/                  # Слайды доклада
```

## Подходы в деталях

### 1. MD-файлы + Cursor Rules

Самый простой подход — контекст хранится в `.cursor/rules/*.mdc` и `AGENTS.md`.

- **Плюсы**: нулевой setup, нет зависимостей, работает из коробки, обновление бесплатно
- **Минусы**: flat text не масштабируется, не видит противоречий, LLM путается при большом контексте
- **v2**: 265/352 (75.3%) — стабильный baseline с минимальной дисперсией (σ=2.08 на Part A)
- **v3**: 256/352 (72.7%, **-2.6%**) — падение на фактах (Part A: 63.0%), стабилен на решениях (Part C: 95.0%)
- **Онбординг**: 53K токенов, $0.032, accuracy 88.8%
- [Подробнее](docs/experiments/13_experiment_md_files.md)

### 2. GitHub Issues MCP

Структурированные задачи через GitHub Issues API.

- **Плюсы**: привычный формат, labels для категоризации, интеграция с workflow
- **Минусы**: нет семантического поиска, ручная структуризация
- **v2**: 262/352 (74.4%)
- **v3**: 267/352 (75.9%, **+1.4%**) — единственный подход с ростом при масштабировании. Лидер Part A (70.3%)
- **Онбординг**: 54K токенов, $0.033, accuracy 88.8%
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)
- [Подробнее](docs/experiments/14_experiment_github_issues.md)

### 3. Mem0 (self-hosted)

Семантическая память поверх PostgreSQL + pgvector.

- **Плюсы**: семантический поиск (p50=101ms), автоматическое извлечение фактов, лучший CPR (2,643)
- **Минусы**: 6 патчей для работы с Cerebras, vendor lock на OpenAI tool calls, dependency hell
- **v2**: 266/352 (75.6%) — лидер v2
- **v3**: 260/352 (73.9%, **-1.7%**) — устаревшие "62 теста" снижают Part A (65.6%). Но лидер Part C (98.8%)
- **Онбординг**: 29K токенов (самый экономный!), $0.018, но accuracy **58.8%** (stale data)
- [Подробнее](docs/experiments/15_experiment_mem0.md)

### 4. Graphiti (getzep) — *вне основной презентации*

Temporal knowledge graph поверх FalkorDB.

- **Плюсы**: архитектурно самый продвинутый (episodes, temporal edges, entity extraction)
- **Минусы**: полный vendor lock на OpenAI Responses API — **не поддерживает** Cerebras, Ollama и другие провайдеры. Бенчмарк проведён с raw fallback (node-текст без реального графа)
- **v2**: 248/352 (70.5%) — raw fallback без графа хуже всех
- **v3**: 261/352 (74.1%, **+3.7%**) — максимальный рост при масштабировании. Node-формат помогает LLM
- **Онбординг**: 53K токенов, $0.032, accuracy 88.8%
- **Статус**: результаты включены в исследование для полноты, но Graphiti **не вошёл в презентацию** из-за vendor lock — невозможно провести честное сравнение без реального графового движка
- [Подробнее](docs/experiments/17_experiment_graphiti.md)

### 5. Helixir MCP (graph + FastThink + causal reasoning)

Графовая память поверх HelixDB с каузальным графом и MCP-инструментами.

- **MCP tools**: `search_memory` + `search_reasoning_chain` (IMPLIES/BECAUSE) + `search_by_concept`
- **Плюсы**: готовые reasoning structures для LLM, работает с Cerebras + Ollama, нет vendor lock
- **Минусы**: ранняя стадия, extraction теряет ~25% контента, нет механизма инвалидации stale данных
- **v2**: 265/352 (75.3%) — 2-е место, стабильно 15-16/16 на «почему?»-вопросах
- **v3**: 255/352 (72.4%, **-2.8%**) — **лидер Part B** (76.2%, граф-рассуждения), но провал Part A (59.9%) из-за stale фактов с confidence 0.83
- **Онбординг**: 170K токенов (3.2x дороже), $0.102, accuracy 75.0% — 15 MCP tool calls, 8.8s
- **Ключевая проблема v3**: каузальный граф отлично хранит стабильные решения, но не отслеживает изменяющиеся факты. "32 теста" подаётся с confidence 0.83, что **хуже чем отсутствие данных**
- **Roadmap**: [Проблемы и план](docs/experiments/18_helixir_issues_and_roadmap.md)

## Бенчмарк

### v2 + v3 — три части

| Часть | Что проверяет | Max | Сценариев |
|-------|--------------|-----|-----------|
| **A** | Базовые задачи (unit-тест, рефакторинг, impact analysis) | 192 | 12 |
| **B** | Связность фактов (multi-hop, causal chains, contradictions) | 80 | 5 |
| **C** | Decision reasoning (хранение «почему», альтернативы, trade-offs) | 80 | 5 |
| **Итого** | | **352** | **22** |

**Методология v2:**
- **3 прогона** с median/mean/stddev
- **Раздельный evaluator**: Generator (gpt-oss-120b) ≠ Evaluator (GLM 4.7) — устраняет bias self-evaluation
- **Шкала 1-4** (4 критерия: accuracy, completeness, context utilization, actionability)
- v2: 175 тестов (21KB), v3: **637 тестов** (29KB контекст)

### Context Recovery Benchmark

Измеряет **стоимость восстановления контекста** — сколько токенов и времени тратит AI
на onboarding через каждый источник. Двухфазный: Phase 1 (retrieval) → Phase 2 (5 вопросов).
Для live-демо на конференции: split-screen с token-счётчиками.

- [Дизайн и методология](docs/benchmark/19_context_recovery_benchmark.md)
- Скрипт: [`benchmark/scripts/benchmark_context_recovery.py`](benchmark/scripts/benchmark_context_recovery.py)
- Дашборд: [`scripts/dashboard_recovery.html`](scripts/dashboard_recovery.html)

### Общий стек

- **LLM (generator)**: Cerebras `gpt-oss-120b`
- **Evaluator (v2)**: Cerebras `zai-glm-4.7` (GLM 4.7 MoE 358B/32B active)
- **Embeddings**: Ollama `nomic-embed-text`

> **Почему Cerebras?** Cerebras — самый быстрый inference-провайдер на рынке (~2000 tok/s output). Для бенчмарка это критично: мы измеряем **скорость извлечения фактов из памяти**, а не латентность модели. Быстрый inference убирает bottleneck LLM и позволяет изолировать влияние именно подхода к контексту. Бонус: низкая цена ($0.60/1M) позволяет делать 3 прогона × 5 подходов × 3 части = 45 запусков без ощутимых расходов.
- [Дизайн бенчмарка](docs/benchmark/12_benchmark_design.md)
- [Полные результаты](docs/benchmark/16_benchmark_results.md)

### Методология расчёта стоимости

Все стоимости рассчитаны по **публичному тарифу Cerebras Inference API** (март 2026):

| Параметр | Значение | Источник |
|----------|---------|----------|
| Input tokens | **$0.60 / 1M tokens** | [cerebras.ai/pricing](https://cerebras.ai/pricing) |
| Output tokens | **$0.60 / 1M tokens** | [cerebras.ai/pricing](https://cerebras.ai/pricing) |
| Embedding (Ollama) | **$0.00** (локально) | Self-hosted nomic-embed-text |
| MCP tool calls | **$0.00** (локально) | Helixir/Mem0 self-hosted |

**Формула расчёта стоимости онбординга:**

```
cost_usd = (input_tokens × 0.60 + output_tokens × 0.60) / 1,000,000
```

Где:
- `input_tokens` = context_tokens (загрузка контекста) + verification_input_tokens (5 вопросов)
- `output_tokens` = verification_output_tokens (ответы модели)
- Для Helixir MCP: input_tokens включают overhead от 15 tool_call циклов (request→response)

**CPR (Cost-Performance Ratio):**

```
CPR = median_quality_score / cost_usd
```

Чем выше CPR — тем больше качества за доллар. Mem0 лидирует по CPR (2,643) за счёт минимальных токенов (29K), но **только при актуальных данных**.

> ⚠️ Стоимость обновления памяти (Mem0: ~30 API calls к embedding, Helixir: rebuild графа) **не включена** в расчёт, т.к. зависит от частоты изменений проекта. Это скрытый OPEX, описанный в [анализе v3](docs/benchmark/20_benchmark_v3_results.md#3-стоимость-обновления-памяти--скрытый-расход).

## Phase 2: Практическая верификация и стоимость обслуживания (2026-04-14)

После бенчмарков мы масштабировали проект (62→336 функций, ~637 прогонов) и проверили
каждый подход на практике — обновление данных, онбординг нового агента, исправление ошибок.

### Стоимость обслуживания по подходам

| Подход | Обновление данных | Сложность | Результат |
|--------|------------------|-----------|-----------|
| **MD-файлы** | Ручное: обновить числа, даты, добавить файлы | Низкая, но OPEX на людях | ✅ Всё обновлено, агент верифицировал |
| **GitHub Issues** | По ходу работы: комменты, чекбоксы, закрытие | **Самая низкая** | ✅ #1-7 закрыты, #10-14 созданы |
| **Mem0** | delete + add_memory, дедупликация блокирует | **Высокая, непредсказуемая** | ⚠️ Часть записей не сохранилась |
| **Helixir** | update_memory + FastThink chains | Средняя (сессии таймаутятся) | ✅ Данные обновлены, цепочка создана |

### Ключевые находки Phase 2

1. **Ложный факт в Mem0** — запись `7fb83211` утверждает, что TestIntegrationProductSearch
   «shares the in-memory database with other tests». В реальности каждый тест изолирован
   через `setupTestDB()` → отдельная `:memory:`. LLM неверно интерпретировал контекст
   при первичном извлечении. Исправить невозможно: `add_memory` возвращает «Added 0 memories»
   (дедупликация), а `update_memory` отсутствует в MCP. Ложный факт с неплохим similarity score
   будет возвращаться при каждом поиске.

2. **Helixir update_memory работает** — эквивалентный ложный факт (`mem_a5945016b15a`)
   был исправлен через `update_memory`. Helixir — единственный подход с семантической памятью,
   где возможна коррекция ошибок без delete+recreate.

3. **FastThink сессии таймаутятся** — между сообщениями в чате сессия может истечь.
   `think_conclude` возвращает «Session not found». Требуется создание новой сессии.
   Рекомендация: выполнять весь цикл think_start→conclude→commit в одном сообщении.

4. **Issues — единственный подход, видимый команде** — комментарий в Issue #14 виден
   всем разработчикам. Обновление записи в Mem0/Helixir видно только следующему AI-агенту.

5. **Онбординговые промты** — созданы 4 стандартизированных промта (XML-структура, роль,
   верификация, пример) для воспроизводимого сравнения подходов. Тестирование в Cursor
   подтвердило корректность всех 4 подходов при актуальных данных.

[Подробный отчёт о верификации](docs/experiments/21_practical_verification.md)

## Портал Bean & Brew

Go-портал (кофейный магазин) — демо-приложение для исследования:

- **Stack**: Go 1.25 + Chi + HTMX + SQLite + Clean Architecture
- **Тесты**: 336 функций (~637 прогонов в `go test -v`) — Entity (237), Handler (179), UseCase (127), Repository (94)
- **Документация**: AGENTS.md + 4 docs + 5 cursor rules + 4 onboarding prompts (всё на русском)
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)

## Tech Stack исследования

| Компонент | Технология | Ссылка |
|-----------|-----------|--------|
| Portal | Go 1.25, chi/v5, HTMX 2.0, SQLite | [go-chi/chi](https://github.com/go-chi/chi) |
| LLM | Cerebras gpt-oss-120b | [cerebras.ai](https://cerebras.ai/) |
| Evaluator | Cerebras zai-glm-4.7 | [cerebras.ai](https://cerebras.ai/) |
| Embeddings | Ollama + nomic-embed-text | [ollama.com](https://ollama.com/) |
| Mem0 | mem0ai/mem0 (self-hosted) | [github.com/mem0ai/mem0](https://github.com/mem0ai/mem0) |
| Graphiti | getzep/graphiti + FalkorDB | [github.com/getzep/graphiti](https://github.com/getzep/graphiti) |
| Helixir | nikita-rulenko/Helixir + HelixDB | [github.com/nikita-rulenko/Helixir](https://github.com/nikita-rulenko/Helixir) |
| HelixDB | helixdb/helix-db | [github.com/helixdb/helix-db](https://github.com/helixdb/helix-db) |
| GitHub MCP | github/github-mcp-server | [github.com/github/github-mcp-server](https://github.com/github/github-mcp-server) |
| Vector Store | pgvector/pgvector (PostgreSQL) | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) |
| Graph DB | FalkorDB | [falkordb.com](https://www.falkordb.com/) |
| MCP SDK | jlowin/fastmcp | [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) |
| AI IDE | Cursor | [cursor.sh](https://cursor.sh/) |

## Воспроизведение бенчмарков

### Требования

- Docker + Docker Compose
- Go 1.25+
- Python 3.12+ с `httpx`
- Ollama с моделью `nomic-embed-text`
- API-ключ Cerebras (`CEREBRAS_API_KEY`)

### Запуск v2

```bash
# 1. Установить зависимости
ollama pull nomic-embed-text
pip install httpx

# 2. Экспортировать ключ
export CEREBRAS_API_KEY=your-key-here

# 3. Бенчмарк Part A (12 сценариев × 3 прогона)
cd benchmark/scripts
python3 benchmark_runner_v2.py md_files ../data/test_context.json 3

# 4. Part B (связность фактов)
python3 benchmark_part_b_v2.py md_files ../data/test_context.json 3

# 5. Part C (decision reasoning)
python3 benchmark_part_c_v2.py md_files ../data/test_context.json 3

# 6. Helixir MCP (требует запущенный HelixDB + Ollama)
python3 benchmark_helixir_mcp.py A 3
python3 benchmark_helixir_mcp.py B 3
python3 benchmark_helixir_mcp.py C 3

# 7. Context Recovery (все подходы)
python3 benchmark_context_recovery.py all
```

Подробная инструкция по каждому подходу — в соответствующих файлах `docs/experiments/`.

## Академические ссылки

- **"Beyond the Context Window"** (arXiv:2603.04814): Cost per turn — fact-memory vs long-context LLM
- **Letta Context-Bench**: Cost-performance ratio для LLM memory providers
- **MemoryAgentBench** (arXiv:2507.05257, ICLR 2026): 4 компетенции — retrieval, learning, long-range, forgetting
- **"How Do Coding Agents Spend Your Money?"** (OpenReview): Token consumption SWE-bench analysis
- **CartoGopher**: Code knowledge graph — 20% token savings, 70-95% на comprehension
- **LoCoMo Benchmark**: Long Context Models evaluation — [arxiv.org/abs/2401.17919](https://arxiv.org/abs/2401.17919)
- **RAG Survey**: Retrieval-Augmented Generation — [arxiv.org/abs/2312.10997](https://arxiv.org/abs/2312.10997)

## Лицензия

Материалы исследования предоставляются для образовательных и научных целей.
