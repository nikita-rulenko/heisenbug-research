# Helixir: Проблемы, статус и план доработки

## Текущий статус: v0.3.1-fix

### Что работает
- `add_memory` — сохраняет факты, извлекает entities, создаёт relations
- `search_memory` — семантический поиск, p50=77ms, p95=82ms
- `search_reasoning_chain` — каузальные цепочки с IMPLIES/BECAUSE рёбрами, deepest_chain=3
- FastThink pipeline — think_start/add/conclude/commit, все 5 decisions сохранены
- MCP интеграция — helixir-mcp binary работает как Cursor MCP server
- Нет vendor lock-in — работает с Cerebras + Ollama

### Эволюция версий

| Версия | Score | Relations | Ключевая проблема |
|--------|-------|-----------|-------------------|
| v0.2.2 | 44.3% | 0 | Over-atomization, hardcoded search scores |
| v0.2.3 | 52.0% | 0 | Extraction потеря контента, позиционный ranking |
| v0.3.1 | 78.4% | 0 | `relations_created: 0` — рёбра не создавались |
| v0.3.1-fix | 71.8%* | **14** | Part A LLM-дисперсия, extraction loss |

\* Part A ниже из-за стохастичности LLM (S2=0, S9=0). Parts B+C стабильны.

---

## Нерешённые проблемы

### P1: Extraction теряет контент (КРИТИЧНО для демо)
**Симптом:** Из 12 эпизодов контекста 3 вернули `memories_added: 0`:
- Episode 7 (Integration tests) → 0 memories
- Episode 8 (Usecase tests) → 0 memories  
- Episode 9 (API tests) → 0 memories

**Последствие:** Система не знает про TestAPIProductCRUD, TestIntegrationProductCRUD и т.д.
На бенчмарке S2 (покрытие endpoint /api/v1/products) получает 0 — потому что API тесты
просто не сохранились.

**Root cause:** LLM (Cerebras gpt-oss-120b) при extraction решает что эпизоды "дублируют"
уже сохранённые факты → returns empty → raw_input fallback не срабатывает
(потому что extraction формально "успешна", просто пустая).

**Как воспроизвести:**
```
add_memory("Integration tests (13 total): TestIntegrationProductCRUD...")
→ memories_added: 0, entities_extracted: 0
```

**Возможное решение:** Если extraction вернула 0 memories — всегда сохранять raw_input.
Сейчас raw_input fallback срабатывает только при ошибке extraction, не при пустом результате.

### P2: FastThink дорогой по времени
**Симптом:** `think_commit` занимает 35-60 секунд на каждое decision.
Для 5 решений: ~4 минуты чистого времени.

**Сравнение:**
- `add_memory` (один факт): 2-5 секунд
- `think_commit` (одно decision): 35-60 секунд (~10x дольше)

**На демо:** Зритель будет ждать минуту на каждое "почему мы так решили".
Либо предзагрузить всё до демо, либо показывать только 1 decision live.

### P3: Score discrimination шире но не идеален
**Симптом:** В v0.3.1-fix scores диапазон 0.49-0.89 (было 0.95-0.45 в v0.3.1).
Это лучше, но всё ещё есть ситуации где нерелевантные факты получают высокий score.

**Пример:** Запрос "Why SQLite not PostgreSQL?" — top result: "TestUnitProductValidate
is a table-driven test" (score 0.86). Это не про SQLite вообще.

**Причина:** nomic-embed-text (768 dims) не различает "Go testing patterns" и
"database choice reasoning" — оба про "проект Bean & Brew".

### P4: D4 (SQLite decision) — 0 entities extracted
**Симптом:** FastThink D4 `think_commit` вернул `entities_extracted: 0, concepts_mapped: 0`.
Memory_id есть (raw fallback), но structured extraction провалилась.

**Последствие:** Нет entity "SQLite" или "PostgreSQL" в графе → reasoning chain для D4
не содержит structured nodes, только raw text.

### P5: search_reasoning_chain — шум в результатах
**Симптом:** При запросе "Why SQLite not PostgreSQL?" — chain возвращает 11 результатов,
из которых ~3 реально про SQLite, остальные про Clean Architecture и тесты.

**Причина:** Chain traversal идёт от seed memories → по рёбрам IMPLIES/BECAUSE.
Если seed нерелевантен (P3), вся цепочка нерелевантна.

### P6: Нет полного сканирования (list all)
**Симптом:** Нет способа получить ВСЕ сохранённые факты без поискового запроса.
`search_memory` возвращает top-N по similarity. Для сценариев типа "найди все дубли"
или "перечисли все тесты" это проблема.

**Есть:** `list_memories` (возвращает первые N), но без фильтрации по типу/теме.

---

## Что можно показывать на демо

### Безопасные демо-сценарии (работают стабильно)
1. **Добавление факта** — `add_memory` с текстом → показать entities_extracted, relations_created
2. **Семантический поиск** — `search_memory("flaky тест")` → найдёт TestIntegrationProductSearch
3. **FastThink запись** — `think_start/add/conclude/commit` для одного decision
4. **Reasoning chain** — `search_reasoning_chain("Why Clean Architecture?")` → IMPLIES/BECAUSE цепочка
5. **Скорость** — search p50=77ms vs Mem0 101ms

### Рискованные демо-сценарии (могут провалиться)
1. **Полнота retrieval** — "Какие API тесты есть?" → может не найти (extraction loss)
2. **D4 reasoning** — "Why SQLite?" → chain шумный
3. **Множественный загрузка** — подряд несколько add_memory → часть может вернуть 0

### Рекомендация для доклада
**Предзагрузить контекст** перед демо (12 эпизодов + 5 decisions). На live показывать:
1. Один `add_memory` → показать extraction
2. Один `search_memory` → показать результат + latency
3. Один `search_reasoning_chain` → показать цепочку Clean Architecture
4. Сравнить с Mem0 search (latency + quality)

---

## План доработки (если есть время до конференции)

### Приоритет 1: P1 — Empty extraction fallback
- Если `memories_added: 0` после extraction → сохранить raw_input как memory
- Это увеличит recall на ~25% (3 потерянных эпизода из 12)
- **Оценка сложности:** изменение в helixir-mcp binary, 1 условие

### Приоритет 2: P3 — Search ranking
- Добавить re-ranking по LLM после vector search
- Или использовать query expansion (расширить запрос перед поиском)
- **Оценка сложности:** средняя, нужен дополнительный LLM-вызов

### Приоритет 3: P2 — FastThink speed
- Параллелизация extraction + relation inference внутри think_commit
- Или кэширование промежуточных результатов
- **Оценка сложности:** высокая, архитектурное изменение

### Приоритет 4: P5 — Chain noise filtering
- Фильтрация chain results по минимальному score threshold
- Или ограничение chain traversal только на high-relevance seeds
- **Оценка сложности:** низкая, параметр в search_reasoning_chain
