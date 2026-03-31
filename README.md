# Heisenbug 2026 — Исследование подходов к управлению контекстом AI-агентов

> Материалы к докладу на [Heisenbug 2026](https://heisenbug.ru/talks/8f09764b2d54406981d189ceb30ef032/)

## О чём исследование

При работе с AI-агентами (Cursor, Copilot, Cline) ключевая проблема — **деградация контекста**:
агент забывает архитектурные решения, дублирует тесты, путает слои приложения.

Мы **практически** сравнили 5 подходов к хранению и управлению контекстом
на примере Go-портала с 175 тестами (241 с подтестами) на 4 уровнях: Unit, Integration, API, UseCase.

### Benchmark v2 — Итоговая таблица (A + B + C = 352 max)

> Generator: gpt-oss-120b → Evaluator: zai-glm-4.7 (GLM 4.7) | Шкала 1-4 | 3 прогона, медиана

| # | Подход | Part A (192) | Part B (80) | Part C (80) | **Итого** | **%** |
|---|--------|:------------:|:-----------:|:-----------:|:---------:|:-----:|
| 1 | **Mem0** (self-hosted) | 125 | 62 | 79 | **266** | **75.6%** |
| 2 | **Helixir MCP** (full tools) | 124 | 63 | 78 | **265** | **75.3%** |
| 2 | **MD-файлы** (.cursor/rules) | 123 | 62 | 80 | **265** | **75.3%** |
| 4 | **GitHub Issues** MCP | 122 | 60 | 80 | **262** | **74.4%** |
| 5 | **Graphiti** (raw fallback) | 107 | 63 | 78 | **248** | **70.5%** |

- **Part A** (12 сценариев): генерация тестов, покрытие, flaky-анализ, рефакторинг, impact analysis
- **Part B** (5 сценариев): multi-hop trace, cross-entity impact, causal chain, contradiction detection
- **Part C** (5 решений): decision reasoning — «почему выбрали X, а не Y»

### Ключевой инсайт: масштаб определяет выбор

**На малом масштабе различий почти нет.** Наш проект — 175 тестов, 21 эпизод контекста (~20K chars,
~5K tokens). Это **полностью помещается в context window** любой современной LLM (128K–200K tokens).
Поэтому все подходы по сути дают LLM один и тот же объём информации — и результат в пределах 1%.

Это важный результат: **для маленьких проектов MD-файлы — оптимальный выбор** (нулевой setup,
максимальная стабильность σ=2.08, и те же 75.3%).

**Когда различия начнут проявляться:**

| Масштаб проекта | Контекст | Что происходит |
|----------------|----------|----------------|
| **< 200 тестов, < 50K chars** | Влезает целиком | Разницы нет — MD-файлы достаточно |
| **200–500 тестов, 50–200K chars** | На грани context window | Семантический поиск (Mem0, Helixir) начинает выигрывать: подаёт релевантные фрагменты вместо всего |
| **500+ тестов, 200K+ chars** | Не влезает | MD-файлы деградируют (нельзя подать всё). RAG обязателен |
| **50+ архитектурных решений** | Конфликтующие rationale | Каузальный граф (Helixir) выигрывает: IMPLIES/BECAUSE рёбра vs плоский список фактов |
| **Длинная история проекта** | Устаревшие решения | Temporal graph (Graphiti) выигрывает: знает что решение X заменено на Y |

**Качественное отличие Helixir MCP** видно уже сейчас на вопросах «почему?»:
`search_reasoning_chain` стабильно даёт 15-16/16 на каузальных вопросах (G3, D1-D5),
тогда как другие подходы показывают разброс 11-16/16. Это потому что LLM получает
**готовую цепочку причин** (`A ← BECAUSE B ← BECAUSE C`), а не набор фактов,
из которых нужно самостоятельно восстановить причинно-следственную связь.

При 50+ решений с пересекающимися и конфликтующими обоснованиями эта разница
станет критической — LLM не сможет «держать в голове» все reasoning chains одновременно.

### Context Recovery Benchmark (демо для конференции)

Дополнительный бенчмарк, измеряющий **стоимость onboarding** AI-агента на проект:
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
│   ├── data/                      #   Контекстные данные (21 эпизод, 5 решений)
│   └── results/                   #   JSON-результаты всех прогонов (21 файл)
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
- **175 тестов** (241 с подтестами), 21 эпизод контекста (~20K chars)

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
- **Тесты**: 175 функций (241 с подтестами) — Unit (entity), Integration (repository), API (handler), Usecase
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
