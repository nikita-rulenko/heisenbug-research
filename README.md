# Heisenbug 2026 — Исследование подходов к управлению контекстом AI-агентов

> Материалы к докладу на [Heisenbug 2026](https://heisenbug.ru/talks/8f09764b2d54406981d189ceb30ef032/)

## О чём исследование

При работе с AI-агентами (Cursor, Copilot, Cline) ключевая проблема — **деградация контекста**:
агент забывает архитектурные решения, дублирует тесты, путает слои приложения.

Мы **практически** сравнили 5 подходов к хранению и управлению контекстом
на примере Go-портала с тестовым покрытием (Unit, Integration, API, E2E):

| # | Подход | Vendor Lock | Setup Time | Итого (A+B+C) |
|---|--------|-------------|------------|----------------|
| 1 | **Helixir** (graph + FastThink) | Нет | ~1 час | **78.4%** |
| 2 | **Graphiti** (raw fallback) | OpenAI | ~30 мин | **75.6%** |
| 3 | **Mem0** (self-hosted) | OpenAI tool calls | ~6 часов | **69.8%** |
| 4 | **GitHub Issues** MCP | GitHub | ~15 мин | **69.6%** |
| 5 | **MD-файлы** (.cursor/rules) | Нет | ~5 мин | **68.8%** |

## Структура репозитория

```
heisenbug-research/
├── docs/                          # Документация исследования
│   ├── background/                #   Обзор литературы и анализ фреймворков
│   ├── experiments/               #   Описание каждого эксперимента
│   └── benchmark/                 #   Дизайн и результаты бенчмарка
│
├── benchmark/                     # Код бенчмарка
│   ├── scripts/                   #   Python-скрипты (runner, part_b, part_c)
│   ├── data/                      #   Контекстные данные (12 эпизодов, 5 решений)
│   └── results/                   #   JSON-результаты всех прогонов
│
├── infra/                         # Инфраструктура
│   ├── mem0/                      #   Docker + patched FastAPI server
│   ├── graphiti/                  #   FalkorDB + graphiti-core SDK
│   ├── helixir-local/             #   HelixDB + helix.toml
│   └── mcp/                       #   MCP-серверы (mem0_mcp_server.py)
│
├── assets/                        # Визуальные материалы
│   ├── diagrams/                  #   D2-диаграммы (src + rendered SVG/PNG)
│   └── tables/                    #   Сравнительные таблицы (PNG)
│
├── presentation/                  # Слайды доклада
├── scripts/                       # Утилиты (генерация таблиц, pptx)
└── research_plan.md               # Исходная спецификация исследования
```

## Подходы в деталях

### 1. MD-файлы + Cursor Rules

Самый простой подход — контекст хранится в `.cursor/rules/*.mdc` и `AGENTS.md`.

- **Плюсы**: нулевой setup, нет зависимостей, работает из коробки
- **Минусы**: flat text не масштабируется, не видит противоречий, LLM путается при большом контексте
- [Подробнее](docs/experiments/13_experiment_md_files.md)

### 2. GitHub Issues MCP

Структурированные задачи через GitHub Issues API.

- **Плюсы**: привычный формат, labels для категоризации, интеграция с workflow
- **Минусы**: нет семантического поиска, ручная структуризация
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)
- [Подробнее](docs/experiments/14_experiment_github_issues.md)

### 3. Mem0 (self-hosted)

Семантическая память поверх PostgreSQL + pgvector.

- **Плюсы**: семантический поиск (p50=101ms), автоматическое извлечение фактов
- **Минусы**: 6 патчей для работы с Cerebras, vendor lock на OpenAI tool calls, dependency hell
- [Подробнее](docs/experiments/15_experiment_mem0.md)

### 4. Graphiti (getzep)

Temporal knowledge graph поверх FalkorDB.

- **Плюсы**: архитектурно самый продвинутый (episodes, temporal edges, entity extraction)
- **Минусы**: полный vendor lock на OpenAI Responses API, бенчмарк с raw fallback
- [Подробнее](docs/experiments/17_experiment_graphiti.md)

### 5. Helixir (graph + FastThink)

Графовая память поверх HelixDB с пайплайном рассуждений.

- **Плюсы**: `search_reasoning_chain` с IMPLIES/BECAUSE рёбрами, работает с Cerebras + Ollama
- **Минусы**: ранняя стадия, extraction теряет ~25% контента, нужна доработка
- **Roadmap**: [Проблемы и план](docs/experiments/18_helixir_issues_and_roadmap.md)

## Бенчмарк

Трёхчастный бенчмарк (500 баллов):

| Часть | Что проверяет | Баллов | Сценариев |
|-------|--------------|--------|-----------|
| **A** | Базовые задачи (unit-тест, рефакторинг, impact analysis) | 250 | 10 |
| **B** | Связность фактов (multi-hop, causal chains, contradictions) | 125 | 5 |
| **C** | Decision reasoning (хранение "почему", альтернативы, trade-offs) | 125 | 5 |

- **LLM**: Cerebras `gpt-oss-120b`
- **Embeddings**: Ollama `nomic-embed-text`
- **Evaluator**: LLM-as-Judge (Cerebras, temperature=0)
- [Дизайн бенчмарка](docs/benchmark/12_benchmark_design.md)
- [Полные результаты](docs/benchmark/16_benchmark_results.md)

## Портал Bean & Brew

Go-портал (кофейный магазин) — демо-приложение для исследования:

- **Stack**: Go + Chi + HTMX + SQLite + Clean Architecture
- **Тесты**: Unit (entity), Integration (repository), API (handler), Usecase
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)

## Tech Stack исследования

| Компонент | Технология | Ссылка |
|-----------|-----------|--------|
| Portal | Go 1.22, chi/v5, HTMX 2.0, SQLite | [go-chi/chi](https://github.com/go-chi/chi) |
| LLM | Cerebras gpt-oss-120b | [cerebras.ai](https://cerebras.ai/) |
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

### Запуск

```bash
# 1. Установить зависимости Ollama
ollama pull nomic-embed-text

# 2. Экспортировать ключ
export CEREBRAS_API_KEY=your-key-here

# 3. Запустить бенчмарк (Part A)
cd benchmark/scripts
python benchmark_runner.py md_files /path/to/context.txt

# 4. Запустить Part B
python benchmark_part_b.py md_files /path/to/context.txt

# 5. Запустить Part C
python benchmark_part_c.py md_files /path/to/context.txt
```

Подробная инструкция по каждому подходу — в соответствующих файлах `docs/experiments/`.

## Академические ссылки

- **LoCoMo Benchmark**: Long Context Models evaluation — [arxiv.org/abs/2401.17919](https://arxiv.org/abs/2401.17919)
- **AgentBench**: Evaluating LLMs as Agents — [arxiv.org/abs/2308.03688](https://arxiv.org/abs/2308.03688)
- **Galileo Evaluation**: LLM-as-Judge methodology — [rungalileo.io](https://www.rungalileo.io/)
- **RAG Survey**: Retrieval-Augmented Generation — [arxiv.org/abs/2312.10997](https://arxiv.org/abs/2312.10997)

## Лицензия

Материалы исследования предоставляются для образовательных и научных целей.
