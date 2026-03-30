# Helixir — Онтологический Memory Framework на HelixDB

## Обзор

**Helixir** — ассоциативный и каузальный AI memory framework, построенный на HelixDB. Позиционируется как "The Fastest Memory for LLM Agents". Это первый фреймворк памяти, построенный поверх HelixDB, использующий его graph-vector возможности.

- **Автор**: Nikita Rulenko
- **GitHub**: [github.com/nikita-rulenko/helixir](https://github.com/nikita-rulenko/helixir)
- **Stars**: 74
- **Язык**: Rust
- **Лицензия**: MIT
- **Релизы**: v0.1.1 (Dec 2025)

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server (stdio)                      │
├─────────────────────────────────────────────────────────────┤
│                      HelixirClient                           │
├───────────────────────────┬─────────────────────────────────┤
│      ToolingManager       │        FastThinkManager         │
│                           │     (in-memory scratchpad)      │
├──────────┬────────┬───────┼─────────────────────────────────┤
│ LLM      │Decision│Entity │  petgraph::StableDiGraph        │
│ Extractor│ Engine │Manager│  (thoughts, entities, concepts) │
├──────────┼────────┼───────┼─────────────────────────────────┤
│ Reasoning│ Search │Ontology│         ↓ commit               │
│ Engine   │ Engine │Manager │         ↓                      │
├──────────┴────────┴───────┴─────────────────────────────────┤
│                      HelixDB Client                          │
├─────────────────────────────────────────────────────────────┤
│                   HelixDB (graph + vector)                   │
└─────────────────────────────────────────────────────────────┘
```

### Ключевые компоненты
- **LLM Extractor** — декомпозиция в атомарные факты
- **Decision Engine** — ADD / UPDATE / SUPERSEDE / NOOP
- **Entity Manager** — управление сущностями и связями
- **Ontology Manager** — типизация: skill, preference, goal, fact, opinion, experience, achievement
- **Reasoning Engine** — каузальные цепочки (IMPLIES, BECAUSE, CONTRADICTS)
- **Search Engine** — vector similarity + graph traversal (SmartTraversalV2)
- **FastThinkManager** — in-memory scratchpad для рассуждений

## Уникальные возможности

### 1. FastThink (Working Memory)
Изолированный scratchpad для сложных рассуждений — не загрязняет основную память:
- `think_start` → `think_add` → `think_recall` → `think_conclude` → `think_commit`
- Лимиты: 100 мыслей, 10 глубина, 30s timeout, 5min TTL
- Timeout recovery — незавершённые мысли сохраняются с маркером `[INCOMPLETE]`

### 2. Онтологическое маппирование
Каждый факт типизируется: skill, preference, goal, fact, opinion, experience, achievement. Это позволяет искать по концепту (`search_by_concept`).

### 3. Cognitive Protocol
Автоматические триггеры recall:
- "remember", "recall" → recent memory search
- "we discussed", "last time" → deep search
- "why did we" → reasoning chains
- "what's next", "plan" → task context

### 4. Temporal Filtering
Четыре режима поиска:
| Mode | Window | Depth | Use case |
|------|--------|-------|----------|
| recent | 4h | 1 | Current session |
| contextual | 30d | 2 | Balanced (default) |
| deep | 90d | 3 | Historical |
| full | All time | 4 | Complete archive |

### 5. Smart Deduplication
Decision engine принимает решения ADD/UPDATE/SUPERSEDE/NOOP для каждого нового факта.

### 6. Semantic Chunking
Автоматическое разбиение длинных текстов на семантические чанки.

## Производительность (Rust)
- ~50ms startup
- ~15MB memory
- Single binary — zero runtime dependencies

## Рекомендуемый стек
- **LLM**: Cerebras (`gpt-oss-120b`, ~3000 tok/s, free tier)
- **Embeddings**: OpenRouter
- Результат: **sub-second memory operations**

## Плюсы

1. **Каузальная память** — не просто факты, а причинно-следственные связи (IMPLIES, BECAUSE, CONTRADICTS)
2. **FastThink** — уникальный in-memory scratchpad для рассуждений, нет аналогов у конкурентов
3. **Онтологическая типизация** — 7 типов фактов, семантический поиск по концептам
4. **Cognitive Protocol** — автоматические триггеры для recall/save
5. **Rust performance** — 50ms startup, 15MB RAM, single binary
6. **Temporal filtering** — 4 режима с разной глубиной
7. **Smart deduplication** — ADD/UPDATE/SUPERSEDE/NOOP
8. **Native MCP** — прямая интеграция с Cursor/Claude Desktop
9. **Open source** (MIT)
10. **Построен на HelixDB** — использует graph-vector capabilities нативно
11. **Timeout recovery** — незавершённые мысли не теряются
12. **Self-hosted** — полный контроль над данными

## Минусы

1. **Ранний проект** — v0.1.1, 74 stars, 21 commit
2. **Один maintainer** — высокий bus factor
3. **Зависимость от HelixDB** — который сам молодой проект
4. **Ограниченная документация** — README-driven
5. **Нет managed SaaS** — только self-hosted
6. **Нет бенчмарков** — не сравнивался с Mem0/Zep на стандартных тестах
7. **Нет enterprise support**
8. **Маленькая экосистема** — нет SDK для Python/JS
9. **Требует LLM для extraction** — дополнительные costs
10. **Нет production case studies**

## Сравнение с Mem0

| Аспект | Helixir | Mem0 |
|--------|---------|------|
| Каузальные связи | IMPLIES, BECAUSE, CONTRADICTS | Нет |
| Working memory | FastThink (scratchpad) | Нет |
| Онтология | 7 типов фактов | Нет типизации |
| Backend | HelixDB (graph+vector native) | Qdrant/Chroma + Neo4j |
| Язык | Rust | Python |
| Startup | ~50ms | ~1-2s |
| Managed SaaS | Нет | Да ($99-499/mo) |
| Stars | 74 | 47.8K |
| Enterprise | Нет | AWS Agent SDK |
| Maturity | v0.1.1 | Production-ready |
| Benchmarks | Нет | LOCOMO (best in class) |
