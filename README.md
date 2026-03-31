# Heisenbug 2026 — Исследование подходов к управлению контекстом AI-агентов

> Материалы к докладу на [Heisenbug 2026](https://heisenbug.ru/talks/8f09764b2d54406981d189ceb30ef032/)

## О чём исследование

При работе с AI-агентами (Cursor, Copilot, Cline) ключевая проблема — **деградация контекста**:
агент забывает архитектурные решения, дублирует тесты, путает слои приложения.

Мы **практически** сравнили 5 подходов к хранению и управлению контекстом
на примере Go-портала на 4 уровнях: Unit, Integration, API, UseCase.

### Benchmark v3 (NEW) — Масштабный тест: 637 тестов

> Проект масштабирован с 175 до **637 тестов** (29KB контекст). Mem0 и Helixir хранят устаревшие данные.

| # | Подход | v2 (175 тестов) | v3 (637 тестов) | Delta |
|---|--------|:--------------:|:--------------:|:-----:|
| 1 | **GitHub Issues** MCP | 262 (74.4%) | **267 (75.9%)** | **+1.4%** |
| 2 | **Graphiti** (raw fallback) | 248 (70.5%) | **261 (74.1%)** | **+3.7%** |
| 3 | **Mem0** (self-hosted) | **266 (75.6%)** | 260 (73.9%) | -1.7% |
| 4 | **MD-файлы** (.cursor/rules) | 265 (75.3%) | 256 (72.7%) | -2.6% |
| 5 | **Helixir MCP** (full tools) | 265 (75.3%) | 255 (72.4%) | **-2.8%** |

### Context Recovery Benchmark (v3) — стоимость онбординга

> **Главная находка v3**: семантическая память требует обслуживания. Устаревшие данные = потеря accuracy.

| Подход | Accuracy | Токены | Стоимость | CPR |
|--------|:--------:|-------:|----------:|----:|
| **MD files** | **88.8%** | 53,195 | $0.032 | 2,225 |
| **GitHub Issues** | **88.8%** | 54,397 | $0.033 | 2,175 |
| **Graphiti** | **88.8%** | 53,402 | $0.032 | 2,216 |
| **Helixir MCP** | 75.0% | 170,668 | $0.102 | 586 |
| **Mem0** | 58.8% | 29,638 | $0.018 | 2,643 |

**Mem0**: accuracy drop **-30pp** (88.8% -> 58.8%) — хранит устаревшие "62 теста" вместо 637.
**Helixir**: потратил **3.2x больше** ($0.102 vs $0.032) токенов, но восстановил только 75%.
**MD/Issues/Graphiti**: получают актуальный контекст напрямую — 88.8% accuracy.

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

- **Part A** (12 сценариев): генерация тестов, покрытие, flaky-анализ, рефакторинг, impact analysis
- **Part B** (5 сценариев): multi-hop trace, cross-entity impact, causal chain, contradiction detection
- **Part C** (5 решений): decision reasoning — «почему выбрали X, а не Y»

### Context Recovery Benchmark (демо для конференции)

Бенчмарк, измеряющий **стоимость onboarding** AI-агента на проект:
сколько токенов, времени и API-вызовов нужно чтобы агент восстановил контекст
через каждый подход. [Дизайн и методология](docs/benchmark/19_context_recovery_benchmark.md).

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

- **Плюсы**: нулевой setup, нет зависимостей, работает из коробки
- **Минусы**: flat text не масштабируется, не видит противоречий, LLM путается при большом контексте
- **v2 результат**: 265/352 (75.3%) — стабильный baseline с минимальной дисперсией (σ=2.08 на Part A)
- [Подробнее](docs/experiments/13_experiment_md_files.md)

### 2. GitHub Issues MCP

Структурированные задачи через GitHub Issues API.

- **Плюсы**: привычный формат, labels для категоризации, интеграция с workflow
- **Минусы**: нет семантического поиска, ручная структуризация
- **v2 результат**: 262/352 (74.4%)
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)
- [Подробнее](docs/experiments/14_experiment_github_issues.md)

### 3. Mem0 (self-hosted)

Семантическая память поверх PostgreSQL + pgvector.

- **Плюсы**: семантический поиск (p50=101ms), автоматическое извлечение фактов
- **Минусы**: 6 патчей для работы с Cerebras, vendor lock на OpenAI tool calls, dependency hell
- **v2 результат**: 266/352 (75.6%) — лидер, но с высокой дисперсией
- [Подробнее](docs/experiments/15_experiment_mem0.md)

### 4. Graphiti (getzep)

Temporal knowledge graph поверх FalkorDB.

- **Плюсы**: архитектурно самый продвинутый (episodes, temporal edges, entity extraction)
- **Минусы**: полный vendor lock на OpenAI Responses API, бенчмарк с raw fallback
- **v2 результат**: 248/352 (70.5%) — raw fallback без графа хуже всех
- [Подробнее](docs/experiments/17_experiment_graphiti.md)

### 5. Helixir MCP (graph + FastThink + causal reasoning)

Графовая память поверх HelixDB с каузальным графом и MCP-инструментами.

- **MCP tools**: `search_memory` + `search_reasoning_chain` (IMPLIES/BECAUSE) + `search_by_concept`
- **Плюсы**: готовые reasoning structures для LLM, работает с Cerebras + Ollama, нет vendor lock
- **Минусы**: ранняя стадия, extraction теряет ~25% контента
- **v2 результат**: 265/352 (75.3%) — 2-е место, стабильно 15-16/16 на «почему?»-вопросах
- **Roadmap**: [Проблемы и план](docs/experiments/18_helixir_issues_and_roadmap.md)

## Бенчмарк

### v2 (текущий) — три части

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
- [Дизайн бенчмарка](docs/benchmark/12_benchmark_design.md)
- [Полные результаты](docs/benchmark/16_benchmark_results.md)

## Портал Bean & Brew

Go-портал (кофейный магазин) — демо-приложение для исследования:

- **Stack**: Go + Chi + HTMX + SQLite + Clean Architecture
- **Тесты**: 637 runs — Entity (237), Handler (179), UseCase (127), Repository (94)
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)

## Tech Stack исследования

| Компонент | Технология | Ссылка |
|-----------|-----------|--------|
| Portal | Go 1.22, chi/v5, HTMX 2.0, SQLite | [go-chi/chi](https://github.com/go-chi/chi) |
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
- Go 1.22+
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
