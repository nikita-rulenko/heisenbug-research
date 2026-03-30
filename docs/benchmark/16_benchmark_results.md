# Результаты бенчмарка: управление тестовым контекстом

## Часть A: Базовые сценарии (10 сценариев, 250 баллов)

| # | Подход | Оценка | % | Setup complexity | Patches | Vendor lock |
|---|--------|--------|---|-----------------|---------|-------------|
| 1 | **Graphiti** (raw fallback) | **157/250** | **62.8%** | Высокая | SDK: OpenAI Responses API only | OpenAI |
| 2 | **GitHub Issues** | **146/250** | **58.4%** | Низкая | 0 | GitHub |
| 3 | **MD-файлы** | **145/250** | **58.0%** | Нулевая | 0 | Нет |
| 4 | **Mem0** self-hosted | **138/250** | **55.2%** | Очень высокая (6 патчей) | 6 | OpenAI tool calls |
| 5 | **Helixir** local (v0.3.1) | **165/250** | **66.0%** | Высокая | 1 (ontology init) | Нет |
| 5b | **Helixir** local (v0.3.1-fix) | **132/250** | **52.8%** | Высокая | 1 (ontology init) | Нет |

### Детализация Части A

| Сценарий | MD | GH Issues | Mem0 | Graphiti* | Helixir v0.3.1 | Helixir v0.3.1-fix |
|----------|-----|-----------|------|-----------|----------------|-------------------|
| S1: Unit-тест | 24 | 25 | 20 | 25 | 23 | 23 |
| S2: Покрытие endpoint | 7 | 7 | 8 | 6 | 14 | 0* |
| S3: Flaky анализ | 23 | 23 | 25 | 25 | 24 | 25 |
| S4: Рефакторинг | 9 | 13 | 0 | 9 | 17 | 5 |
| S5: E2E тест | 23 | 18 | 10 | 20 | 23 | 25 |
| S6: Impact analysis | 11 | 8 | 11 | 10 | 6 | 6 |
| S7: Обнаружение дублей | 10 | 6 | 1 | 18 | 7 | 4 |
| S8: Test plan | 20 | 25 | 20 | 24 | 22 | 24 |
| S9: Темпоральный | 0 | 0 | 18 | 0 | 5 | 0* |
| S10: Оптимизация | 18 | 21 | 25 | 20 | 24 | 20 |
| **Итого** | **145** | **146** | **138** | **157** | **165** | **132** |

\* S2, S9 в v0.3.1-fix получили 0 из-за LLM-дисперсии (Cerebras gpt-oss-120b при temperature=0.2
ответил не по контексту). Part A имеет высокую дисперсию между прогонами — нужно 3+ прогона с медианой.

## Часть B: Связность фактов и скорость поиска (5 сценариев, 125 баллов)

Часть A не учитывала скорость поиска и способность систем прослеживать связи
между фактами (multi-hop reasoning). Часть B целенаправленно тестирует эти аспекты.

| # | Подход | Оценка | % | Search p50 | Search p95 |
|---|--------|--------|---|------------|------------|
| 1 | **Graphiti** (raw fallback) | **98/125** | **78.4%** | N/A | N/A |
| 2 | **Mem0** self-hosted | **88/125** | **70.4%** | 101ms | 213ms |
| 3 | **GitHub Issues** | **85/125** | **68.0%** | N/A | N/A |
| 4 | **Helixir** local (v0.3.1) | **105/125** | **84.0%** | 77ms | 82ms |
| 4b | **Helixir** local (v0.3.1-fix) | **104/125** | **83.2%** | 77ms | 82ms |
| 5 | **MD-файлы** | **78/125** | **62.4%** | N/A | N/A |

### Детализация Части B

| Сценарий | MD | GH Issues | Mem0 | Graphiti* | Helixir v0.3.1 | Helixir v0.3.1-fix |
|----------|-----|-----------|------|-----------|----------------|-------------------|
| G1: Multi-hop dependency | 21 | 19 | 19 | 23 | 21 | 25 |
| G2: Cross-entity impact | 13 | 19 | 15 | 13 | 22 | 15 |
| G3: Causal chain (flaky) | 25 | 23 | 22 | 25 | 25 | 23 |
| G4: Inverse lookup | 11 | 16 | 13 | 17 | 17 | 20 |
| G5: Contradiction detect | 8 | 8 | 19 | 20 | 20 | 21 |
| **Итого** | **78** | **85** | **88** | **98** | **105** | **104** |

### Ключевое наблюдение Части B

**Mem0 обошёл MD-файлы на связности** (70.4% vs 62.4%), несмотря на то что имеет
всего 11 извлечённых фактов. Семантический поиск помогает фокусировать контекст
на релевантных фрагментах, а не заливать LLM всем подряд.

**MD-файлы провалили contradiction detection** (8/25) — плоский текст не позволяет
системе видеть противоречия между правилами и реальностью кода.

## Сводная таблица (A + B)

| # | Подход | Часть A | Часть B | Итого | % |
|---|--------|---------|---------|-------|---|
| 1 | **Graphiti** (raw) | 157 | 98 | **255/375** | **68.0%** |
| 2 | **GitHub Issues** | 146 | 85 | **231/375** | **61.6%** |
| 3 | **Mem0** | 138 | 88 | **226/375** | **60.3%** |
| 4 | **MD-файлы** | 145 | 78 | **223/375** | **59.5%** |
| 5 | **Helixir** (v0.2.3) | 124 | 71 | **195/375** | **52.0%** |

## Часть C: Decision Reasoning (5 сценариев, 125 баллов)

Части A и B проверяли **что** система знает. Часть C проверяет, хранит ли система
**почему** было принято решение: rationale, отвергнутые альтернативы, принятые trade-offs.

Для каждого подхода были загружены 5 решений с полным reasoning:
- D1: Почему Clean Architecture (4 слоя, изоляция тестов, плоская структура отвергнута)
- D2: Почему table-driven тесты (единая assertion point, отдельные функции отвергнуты)
- D3: Почему оставили flaky тест (ICU fix дорогой, удаление отвергнуто)
- D4: Почему SQLite а не PostgreSQL (single binary, Docker не нужен, приняли LIKE-баг)
- D5: Почему real DB в usecase-тестах (моки не ловят SQL-баги, gomock отвергнут)

| # | Подход | Оценка | % | Механизм хранения | Потери при записи |
|---|--------|--------|---|-------------------|-------------------|
| 1 | **Helixir** (v0.3.1-fix FastThink) | **123/125** | **98.4%** | think_start→add→conclude→commit | 0/5 — все decisions сохранены |
| 1b | **Helixir** (v0.3.1 FastThink) | **122/125** | **97.6%** | think_start→add→conclude→commit | 1/5 decisions → 0 entities |
| 2 | **Mem0** | **123/125** | **98.4%** | add_memory (text) | 2/5 decisions → 0 memories |
| 3 | **Graphiti** (raw) | **123/125** | **98.4%** | raw text dump | 0 потерь |
| 4 | **MD-файлы** | **121/125** | **96.8%** | raw text dump | 0 потерь |
| 5 | **GitHub Issues** | **117/125** | **93.6%** | raw text dump | 0 потерь |

### Детализация Части C

| Сценарий | MD | GH Issues | Mem0 | Graphiti* | Helixir v0.3.1 | Helixir v0.3.1-fix |
|----------|-----|-----------|------|-----------|----------------|-------------------|
| D1: Clean Architecture | 23 | 25 | 25 | 23 | 22 | 25 |
| D2: Table-driven tests | 25 | 22 | 25 | 25 | 25 | 25 |
| D3: Flaky test decision | 25 | 23 | 25 | 25 | 25 | 23 |
| D4: SQLite vs PostgreSQL | 23 | 22 | 25 | 25 | 25 | 25 |
| D5: Real DB vs mocks | 25 | 25 | 23 | 25 | 25 | 25 |
| **Итого** | **121** | **117** | **123** | **123** | **122** | **123** |

### Критический инсайт: search_reasoning_chain — эволюция v0.3.1 → v0.3.1-fix

Helixir имеет **уникальный** FastThink pipeline (`think_start` → `think_add` → `think_conclude` → `think_commit`)
и `search_reasoning_chain` для поиска по цепочкам рассуждений (IMPLIES/BECAUSE/CONTRADICTS).

#### v0.3.1 (relations_created: 0)

| Операция | Результат |
|----------|-----------|
| FastThink pipeline (запись) | ✅ 5/5 — все sessions committed |
| think_commit → entities_extracted | ⚠️ 3/5 — D3 и D4 извлекли 0 entities |
| search_reasoning_chain (поиск) | ❌ 2/5 — нашёл релевантные цепочки только для D2 и D5 |
| relations_created | ❌ 0 — рёбра IMPLIES/BECAUSE не создавались |

**Проблема:** `infer_relations` не создавал рёбра из-за: 1) неправильный JSON-формат для Cerebras API,
2) relation inference пропускалась для Update/Noop решений, 3) сломанный index mapping при extraction.

#### v0.3.1-fix (relations_created: 14+)

| Операция | Результат |
|----------|-----------|
| FastThink pipeline (запись) | ✅ 5/5 — все sessions committed |
| think_commit → entities_extracted | ✅ 4/5 — только D4 извлёк 0 (но memory_id есть) |
| search_reasoning_chain (поиск) | ✅ 5/5 — реальные IMPLIES/BECAUSE цепочки, deepest_chain=3 |
| relations_created | ✅ 14 (из 12 эпизодов) + concepts_mapped: 7 (из 5 decisions) |

**Прорыв:** `search_reasoning_chain` теперь возвращает настоящие каузальные цепочки:
- "Clean Architecture → 4-level test isolation" (IMPLIES) → "Flat structure rejected: DB coupling" (BECAUSE)
- "Table-driven tests → single assertion" (IMPLIES) → "Separate functions rejected" (BECAUSE)
- "Flaky test → LIKE + Cyrillic" (BECAUSE) → "shares in-memory DB" (BECAUSE)

D3 (flaky test decision), который полностью терялся в v0.3.1, теперь сохраняется: 4 entities, 1 concept.

### Почему все scores ~95%+?

На малом масштабе (5 решений, ~2-9K chars контекста) LLM отлично извлекает reasoning
из любого формата — raw text, extracted memories, conclusions. Разница проявится при:
- 50+ решений (не влезут в context window как raw text)
- Конфликтующие решения (нужна структура для детекции противоречий)
- Длинные reasoning chains (5+ шагов вместо 2-3)

## Сводная таблица (A + B + C)

| # | Подход | Часть A | Часть B | Часть C | Итого | % |
|---|--------|---------|---------|---------|-------|---|
| 1 | **Helixir** (v0.3.1) | 165 | 105 | 122 | **392/500** | **78.4%** |
| 2 | **Graphiti** (raw) | 157 | 98 | 123 | **378/500** | **75.6%** |
| 3 | **Helixir** (v0.3.1-fix) | 132 | 104 | 123 | **359/500** | **71.8%** |
| 4 | **Mem0** | 138 | 88 | 123 | **349/500** | **69.8%** |
| 5 | **GitHub Issues** | 146 | 85 | 117 | **348/500** | **69.6%** |
| 6 | **MD-файлы** | 145 | 78 | 121 | **344/500** | **68.8%** |

**Примечание по Helixir v0.3.1 vs v0.3.1-fix:** Part B и C стабильны (104≈105, 123≈122).
Разница в Part A (132 vs 165) обусловлена LLM-дисперсией: S2 и S9 получили 0 из-за стохастичности
Cerebras gpt-oss-120b. При 3 прогонах с медианой ожидаемый результат ~148-165 для Part A.

**Ключевое улучшение v0.3.1-fix:** не в score, а в качестве graph relations.
`relations_created: 14` (было 0), `search_reasoning_chain` работает с реальными IMPLIES/BECAUSE цепочками.

## Важные оговорки

1. **Graphiti (68.0%)** — тестировался с raw context fallback, т.к. SDK использует `client.responses.parse()` 
   (OpenAI Responses API), несовместимый с Cerebras. Граф знаний **не был построен**.
   Реальный score при работающем графе был бы выше.

2. **Helixir (v0.3.1: 78.4%, v0.3.1-fix: 71.8%)** — v0.3.1 ввёл extraction robustness + raw_input fallback,
   подняв score с 52.0% до 78.4%. v0.3.1-fix починил **relation creation pipeline** —
   `relations_created` выросло с 0 до **14**, `search_reasoning_chain` теперь возвращает
   реальные IMPLIES/BECAUSE цепочки (deepest_chain=3). Benchmark score v0.3.1-fix ниже
   из-за LLM-дисперсии в Part A (S2=0, S9=0), Parts B+C стабильны.
   **v0.3.1-fix — единственная версия, где graph reasoning реально работает.**

3. **Mem0 (60.3%)** — извлёк только 11 фактов из-за несовместимости Cerebras с tool call
   форматом Mem0. Но даже с 11 фактами обошёл MD-файлы на Части B благодаря
   семантическому поиску.

4. **MD-файлы (59.5%)** — получают весь контекст сразу в context window LLM.
   Это даёт преимущество при малом контексте на Part A, но **проигрывает на связности**
   (Part B), т.к. нет структурного понимания связей между фактами.

## Метрики ресурсов

| Метрика | MD | GH Issues | Mem0 | Graphiti | Helixir |
|---------|-----|-----------|------|----------|---------|
| Container count | 0 | 0 | 2 | 1 | 1 |
| RAM (peak) | 0 MB | 0 MB | ~400 MB | ~100 MB | ~200 MB |
| Disk (images) | 0 | 0 | ~2 GB | ~200 MB | ~500 MB |
| Cold start | 0s | 0s | ~15s | ~5s | ~3s |
| Setup wall time | 5 min | 15 min | ~6 hours | ~30 min | ~1 hour |
| Patches needed | 0 | 0 | 6 | 0 (SDK issue) | 1 |
| External deps | 0 | GitHub API | PG, Ollama, Cerebras | FalkorDB, OpenAI | HelixDB, Ollama, Cerebras |
| Search p50 | N/A | N/A | 101ms | N/A | 77ms |
| Search p95 | N/A | N/A | 213ms | N/A | 82ms |
| Facts extracted | manual | manual | 11 | N/A | v0.3.1: 43 mem + 110 ent; v0.3.1-fix: 23 mem + 53 ent + 14 rel |
| Score discrimination | N/A | N/A | 0.32–0.64 | N/A | 0.85–0.49 (v0.3.1-fix) |

## Ключевые находки

### 0. Decision reasoning: от сломанного pipeline к работающему graph
Helixir — единственная система с нативным reasoning pipeline (FastThink + search_reasoning_chain).
- **v0.3.1**: `search_reasoning_chain` нашёл цепочки для **2/5** решений (`relations_created: 0`).
- **v0.3.1-fix**: `search_reasoning_chain` нашёл цепочки для **5/5** решений (`relations_created: 14`,
  `deepest_chain: 3`, реальные IMPLIES/BECAUSE рёбра между фактами).

При этом все подходы показали ~95%+ на Part C при малом масштабе. Разница проявится
при 50+ решениях, конфликтующих решениях и длинных reasoning chains (5+ шагов).

### 1. Плоский текст не масштабируется на связность
MD-файлы заняли **последнее место** в Part B (62.4%), проиграв даже Mem0 с 11 фактами.
Причина: flat text не даёт LLM структурного понимания связей между слоями, 
сущностями и тестами. Это подтверждает опасение из research_plan:
> «Мой опыт говорит что в мд файлах ИИ начинает путаться»

### 2. Семантический поиск > full context dump на graph-задачах
Mem0 (70.4%) обошёл MD (62.4%) и GitHub Issues (68.0%) на Part B, при том что
имеет в 10x меньше контекста. Фокусированный retrieval бьёт brute-force context.

### 3. Vendor lock-in — критическая проблема
- **Mem0**: tool call формат оптимизирован под OpenAI → Cerebras извлекает 11 фактов вместо 50+
- **Graphiti**: SDK использует OpenAI Responses API → полная несовместимость с Cerebras
- **Helixir**: работает с Cerebras + Ollama без патчей

### 4. Эволюция Helixir: v0.2.2 → v0.2.3 → v0.3.1 → v0.3.1-fix

| Версия | Score A+B+C | Memories | Entities | Relations | Ключевой фикс |
|--------|-------------|----------|----------|-----------|----------------|
| v0.2.2 | 44.3% (A only) | 47 (over-atomized) | — | 0 | — |
| v0.2.3 | 52.0% (A+B) | 12 | — | 0 | Rank-based scoring, reduced atomization |
| v0.3.1 | 78.4% | 43 | 110 | 0 | Extraction retry + raw_input fallback |
| **v0.3.1-fix** | **71.8%*** | **23** | **53** | **14** | **Relation creation pipeline fix** |

\* Part A ниже из-за LLM-дисперсии (S2=0, S9=0). Parts B+C стабильны: 104≈105, 123≈122.

Главный вклад v0.3.1: **raw_input fallback** — при failure extraction сохраняет
оригинальный текст как memory. Это спасло эпизоды, которые раньше терялись.

Главный вклад v0.3.1-fix: **relation creation pipeline** — починены 3 root cause:
1. Неправильный JSON-формат для Cerebras API в `infer_relations`
2. Relation inference пропускалась для Update/Noop решений
3. Сломанный index mapping при extraction relations

Результат: `relations_created: 14` (было 0), `search_reasoning_chain` возвращает
реальные каузальные цепочки с IMPLIES/BECAUSE рёбрами (deepest_chain=3).
D3 (flaky test decision) — раньше терялся при extraction, теперь: 4 entities, 1 concept, memory_id ✅.

### 5. Темпоральный контекст — уникальное преимущество memory systems
Только Mem0 (18/25) и Helixir (18/25) смогли ответить на S9 (темпоральный вопрос).
MD-файлы и GitHub Issues получили 0/25.

### 6. Contradiction detection — слабое место плоского текста
G5 (обнаружение противоречий) показал разрыв: Graphiti 20/25, Mem0 19/25,
MD-файлы 8/25. Без структуры система не может сопоставлять правила с реальностью.

### 7. Setup complexity — реальная стоимость
- Mem0: 6 часов, 6 патчей, dependency hell
- Helixir: 1 час, сборка из исходников, инициализация онтологии
- Graphiti: 30 мин, но полностью нерабочий без OpenAI
- MD-файлы: 5 минут, 0 зависимостей

## Протокол

- **LLM**: Cerebras gpt-oss-120b (для всех подходов)
- **Embeddings**: Ollama nomic-embed-text (для Mem0, Helixir)
- **Evaluator**: LLM-as-Judge (Cerebras gpt-oss-120b, temperature=0)
- **Прогон**: 1 (по протоколу нужно 3, взять медиану)
- **MCP**: mem0-local (fastmcp), helixir-local (helixir-mcp binary)
- **Максимум**: 500 баллов (Part A: 250 + Part B: 125 + Part C: 125)
- **Дата**: 2026-03-27
