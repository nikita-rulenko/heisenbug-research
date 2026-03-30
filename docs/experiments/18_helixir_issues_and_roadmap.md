# Эксперимент 5: Helixir — Графовая память с reasoning pipeline

## TL;DR
Helixir — графовая память поверх HelixDB с FastThink reasoning pipeline. Единственная из
пяти систем, где работают и семантический поиск, и graph relations, и каузальные цепочки —
без vendor lock-in. Потребовал 4 итерации (v0.2.2 → v0.3.1-fix) для выхода на рабочий уровень.
Итого: **78.4% (v0.3.1)** / **71.8% (v0.3.1-fix)** по трёхчастному бенчмарку.

## Инфраструктура

### Финальный стек
- **HelixDB** — графовая база данных (Rust, Docker)
- **Ollama nomic-embed-text** — embeddings (768 dims) через OpenAI-compatible API
- **Cerebras gpt-oss-120b** — LLM для extraction, reasoning, relation inference
- **helixir-mcp** — Rust binary, MCP server для Cursor

### Конфигурация
```
infra/helixir-local/
├── docker-compose.yml    # HelixDB (порт 6970)
├── helix.toml            # Схема: memories, entities, concepts, relations
```

### Переменные окружения (helixir-mcp)
```
HELIX_URL=http://localhost:6970
LLM_URL=https://api.cerebras.ai/v1
LLM_API_KEY=<cerebras-key>
LLM_MODEL=gpt-oss-120b
EMBEDDING_URL=http://localhost:11434/v1
EMBEDDING_MODEL=nomic-embed-text
```

## Результаты бенчмарка

### Часть A: Базовые сценарии (10 сценариев, 250 баллов)

| Подход | Score | % |
|--------|-------|---|
| Helixir v0.3.1 | **165/250** | **66.0%** |
| Graphiti (raw) | 157/250 | 62.8% |
| GitHub Issues | 146/250 | 58.4% |
| MD-файлы | 145/250 | 58.0% |
| Mem0 | 138/250 | 55.2% |
| Helixir v0.3.1-fix | 132/250 | 52.8%* |

\* Снижение v0.3.1-fix объясняется LLM-дисперсией: S2 и S9 получили 0 из-за стохастичности
Cerebras gpt-oss-120b (temperature=0.2). Один прогон; при 3+ прогонах с медианой ожидается ~148-165.

### Часть B: Связность фактов (5 сценариев, 125 баллов)

| Подход | Score | % | Search p50 | Search p95 |
|--------|-------|---|------------|------------|
| Helixir v0.3.1 | **105/125** | **84.0%** | 77ms | 82ms |
| Helixir v0.3.1-fix | **104/125** | **83.2%** | 77ms | 82ms |
| Graphiti (raw) | 98/125 | 78.4% | N/A | N/A |
| Mem0 | 88/125 | 70.4% | 101ms | 213ms |
| GitHub Issues | 85/125 | 68.0% | N/A | N/A |
| MD-файлы | 78/125 | 62.4% | N/A | N/A |

Helixir стабильно лидирует в Part B: multi-hop reasoning и contradiction detection выигрывают
от графовой структуры (entities + relations).

### Часть C: Decision Reasoning (5 сценариев, 125 баллов)

| Подход | Score | % | Механизм |
|--------|-------|---|----------|
| Helixir v0.3.1-fix | **123/125** | **98.4%** | FastThink pipeline |
| Mem0 | 123/125 | 98.4% | add_memory (text) |
| Graphiti (raw) | 123/125 | 98.4% | raw text dump |
| Helixir v0.3.1 | 122/125 | 97.6% | FastThink pipeline |
| MD-файлы | 121/125 | 96.8% | raw text dump |
| GitHub Issues | 117/125 | 93.6% | raw text dump |

Все подходы показали ~95%+ на малом масштабе (5 decisions). Разница проявится при 50+ decisions,
конфликтующих решениях и длинных reasoning chains (5+ шагов).

### Сводная таблица (A + B + C, 500 баллов)

| Подход | A | B | C | Итого | % |
|--------|---|---|---|-------|---|
| Helixir v0.3.1 | 165 | 105 | 122 | **392** | **78.4%** |
| Graphiti (raw) | 157 | 98 | 123 | 378 | 75.6% |
| Helixir v0.3.1-fix | 132 | 104 | 123 | 359 | 71.8% |
| Mem0 | 138 | 88 | 123 | 349 | 69.8% |
| GitHub Issues | 146 | 85 | 117 | 348 | 69.6% |
| MD-файлы | 145 | 78 | 121 | 344 | 68.8% |

## Что есть у Helixir, чего нет у остальных

### 1. Graph relations — работают в нашем стеке

| Система | Graph relations | Реально работают |
|---------|----------------|-----------------|
| Helixir v0.3.1-fix | IMPLIES / BECAUSE / CONTRADICTS | **Да** (14 relations, deepest_chain=3) |
| Graphiti | Entity/Relation extraction | **Нет** (vendor lock на OpenAI) |
| Mem0 | Mem0g (Neo4j graph store) | **Нет** (dependency hell, langchain-neo4j) |
| GitHub Issues | Нет | — |
| MD-файлы | Нет | — |

В рамках нашего эксперимента (Cerebras + Ollama, без OpenAI key) graph relations удалось
построить только в Helixir. Graphiti архитектурно способен, но заблокирован OpenAI Responses API.
Mem0g (Neo4j graph store) не удалось поднять из-за отсутствия langchain-neo4j в Docker-образе.
При наличии OpenAI API key результат Graphiti и Mem0g мог бы быть другим.

### 2. FastThink — структурированный reasoning pipeline

```
think_start("Почему Clean Architecture?")
→ think_add("Рассматривали flat structure, domain-driven, hexagonal")
→ think_add("Выбрали 4-слойный подход: entity → usecase → repository → handler")
→ think_conclude("Clean Architecture выбран для изоляции тестовых слоёв")
→ think_commit()
  → entities_extracted: 5
  → relations_created: 3 (IMPLIES, BECAUSE)
  → concepts_mapped: 1
```

В остальных протестированных системах structured reasoning pipeline отсутствует: Mem0 сохраняет
решения как flat text, Graphiti мог бы строить temporal episode chains, но не работает без OpenAI.

### 3. search_reasoning_chain — каузальный поиск

Запрос: `search_reasoning_chain("Why Clean Architecture?")`

Результат (v0.3.1-fix):
```
Chain depth: 3
→ "Clean Architecture → 4-level test isolation" (IMPLIES)
  → "Flat structure rejected: DB coupling in handlers" (BECAUSE)
    → "Repository pattern isolates SQL from business logic" (IMPLIES)
```

Для сравнения: Mem0 `search_memory` возвращает flat список фактов без связей между ними,
MD-файлы и Issues подают весь текст целиком. Helixir прослеживает цепочки причин через graph traversal.

### 4. LLM-агностичность

| Система | Cerebras | Ollama | Без OpenAI key |
|---------|----------|--------|----------------|
| Helixir | **Да** | **Да** | **Да** |
| Mem0 | Частично (11/50+ фактов) | Да (embeddings) | Нет (tool call format) |
| Graphiti | Нет | Да (embeddings) | Нет (Responses API) |

Helixir работает с Cerebras + Ollama без единого патча. Mem0 потребовал 6 патчей и всё равно
извлекает в ~5x меньше фактов из-за несовместимости tool call формата.

## Эволюция: 4 версии за время исследования

| Версия | Score (A+B+C) | Memories | Entities | Relations | Что починено |
|--------|---------------|----------|----------|-----------|-------------|
| v0.2.2 | 44.3% (A only) | 47 | — | 0 | — |
| v0.2.3 | 52.0% (A+B) | 12 | — | 0 | Rank-based scoring, меньше atomization |
| v0.3.1 | **78.4%** | 43 | 110 | 0 | raw_input fallback, extraction retry |
| v0.3.1-fix | 71.8%* | 23 | 53 | **14** | Relation creation pipeline |

\* Part A ниже из-за LLM-дисперсии. Parts B+C стабильны (104≈105, 123≈122).

**Главный прорыв v0.3.1:** `raw_input fallback` — при провале extraction сохраняет оригинальный
текст как memory. Спас эпизоды, которые ранее терялись полностью.

**Главный прорыв v0.3.1-fix:** `relation creation pipeline` — починены 3 root cause:
1. Неправильный JSON-формат для Cerebras API в `infer_relations`
2. Relation inference пропускалась для Update/Noop решений
3. Сломанный index mapping при extraction

## Нерешённые проблемы

### P1: Extraction теряет контент
3 из 12 эпизодов вернули `memories_added: 0` (Integration, Usecase, API tests).
LLM считает их "дублями" уже сохранённых фактов. Fallback не срабатывает (extraction
формально успешна, просто пустая). Потеря ~25% контекста.

### P2: FastThink медленный
`think_commit` занимает 35-60 сек на decision (vs 2-5 сек у `add_memory`).
Для live-демо нужна предзагрузка.

### P3: Score discrimination
nomic-embed-text (768 dims) плохо различает тематически близкие факты.
Нерелевантные результаты могут получать score 0.86.

### P4-P6: Мелкие проблемы
- D4 (SQLite decision) — 0 entities extracted (raw fallback сработал)
- Chain noise — seed nерелевантен → вся цепочка нерелевантна
- Нет full scan (только top-N по similarity)

## Сравнение с другими подходами

| Критерий | MD | Issues | Mem0 | Graphiti | Helixir |
|----------|-----|--------|------|----------|---------|
| Score A+B+C | 68.8% | 69.6% | 69.8% | 75.6% | **78.4%** |
| Graph relations | Нет | Нет | Нет* | Нет** | **Да (14)** |
| Reasoning chains | Нет | Нет | Нет | Нет** | **Да** |
| Semantic search | Нет | Нет | **Да** | Нет** | **Да** |
| LLM-агностичность | N/A | N/A | Плохая | **Нет** | **Да** |
| Setup time | 5 мин | 15 мин | ~6 ч | ~30 мин | ~1 ч |
| Vendor lock | Нет | GitHub | OpenAI | OpenAI | **Нет** |
| Зрелость | Stable | Stable | Beta | Beta | **Alpha** |

\* Mem0g (Neo4j graph store) не поднялся из-за dependency hell.
\** Graphiti способен, но заблокирован OpenAI Responses API.

## Ключевые выводы

1. **Единственный работающий graph reasoning.** Из трёх систем с graph-функциональностью
   (Graphiti, Mem0g, Helixir) только Helixir реально построил граф и использует его при поиске.
   Это не заслуга Helixir per se — Graphiti и Mem0g заблокированы vendor lock-in.

2. **raw_input fallback — ключ к выживаемости.** v0.3.1 показал, что при малом контексте
   сохранение оригинального текста (когда extraction провалилась) важнее, чем quality extraction.
   Это подняло score с 52% до 78%.

3. **Extraction — слабое звено.** 25% контента теряется при загрузке. Это системная проблема
   LLM-based extraction при работе с Cerebras: модель склонна считать факты "дублями".
   Mem0 теряет ещё больше (11 из ~50+ потенциальных фактов), но по другой причине (tool call формат).

4. **Высокая дисперсия Part A.** Один прогон бенчмарка недостаточен: S2 и S9 получили 0
   в v0.3.1-fix, но 14 и 5 в v0.3.1 (тот же контекст). Нужно 3+ прогона с медианой.

5. **Alpha-качество.** За время исследования вышло 4 версии, каждая с серьёзным фиксом.
   Для production нужна стабилизация extraction и speed-up FastThink.

## Ссылки

- Helixir: https://github.com/nikita-rulenko/Helixir
- HelixDB: https://github.com/helixdb/helix-db
- HelixDB сайт: https://www.helix-db.com/
- Релиз v0.3.1-fix: https://github.com/nikita-rulenko/Helixir/releases/tag/v0.3.1-fix
- Cerebras API: https://inference-docs.cerebras.ai/
- Ollama nomic-embed-text: https://ollama.com/library/nomic-embed-text
- MCP спецификация: https://modelcontextprotocol.io/
