# Benchmark: Context Recovery Cost (Демо для Heisenbug 2026)

## Идея

Измерить **стоимость "onboarding" AI-агента** на проект при разных подходах к хранению контекста.
Открываем новый диалог, указываем источник контекста через MCP, и замеряем:
- Сколько **токенов** (input/output) потребовалось
- Сколько **сообщений/turns** до первого правильного ответа
- Сколько **секунд** заняло восстановление контекста
- Какой **% правильных ответов** после onboarding

Это будет **живое демо на конференции**: split-screen сравнение 5 подходов.

## Существующие исследования

### Прямые аналоги

| Работа | Что измеряет | Наш gap |
|--------|-------------|---------|
| **"Beyond the Context Window"** (arXiv:2603.04814) | Cost per turn: fact-memory vs long-context LLM. Break-even ~10 turns при 100K ctx | Не coding-specific, не сравнивает graph memory |
| **Letta Context-Bench** | Cost-performance ratio: accuracy vs $$. Claude 4.5 = 74% / $24.58 | Не про onboarding, а про задачи с памятью |
| **MemoryAgentBench** (arXiv:2507.05257, ICLR 2026) | 4 компетенции: retrieval, learning, long-range, forgetting | Multi-turn conversational, не project context |
| **"How Do Coding Agents Spend Your Money?"** (OpenReview) | Token consumption SWE-bench. Input tokens dominate, 10x variance | Task completion, не context recovery |
| **CartoGopher** | Code knowledge graph: 20% token savings, 70-95% на comprehension | Graph-specific, не multi-approach comparison |

### Ключевой инсайт из литературы

> AI coding agents тратят **70-80% токенов** на "orientation" — чтение файлов, поиск по коду,
> навигацию. Только 20-30% уходит на собственно решение задачи.

Наш бенчмарк измеряет именно эту orientation-фазу при разных подходах к хранению контекста.

### Чего НЕ существует (наша ниша)

Никто не строил бенчмарк, который сравнивает **стоимость project onboarding** через разные
context sources (MD файлы, RAG, graph memory, issue trackers, MCP серверы) на одном проекте
с одними и теми же вопросами.

## Дизайн бенчмарка

### Подходы (5 источников контекста)

| # | Подход | MCP инструмент | Формат контекста |
|---|--------|---------------|-----------------|
| 1 | **MD-файлы** | `Read` (файлы из repo) | Плоский текст, ~20K chars |
| 2 | **GitHub Issues** | `mcp__github` | Структурированные issues |
| 3 | **Mem0** | `mcp__mem0-local__search_memory` | Семантический поиск, top-K |
| 4 | **Helixir MCP** | `search_memory` + `search_reasoning_chain` + `search_by_concept` | Каузальные цепочки + онтология |
| 5 | **Graphiti** | (raw fallback) | Граф знаний (если доступен) |

### Метрики (из литературы)

| Метрика | Описание | Источник |
|---------|----------|----------|
| **Input tokens** | Токены контекста, потреблённые при чтении | SWE-bench analysis |
| **Output tokens** | Токены ответов AI | SWE-bench analysis |
| **Total cost ($)** | API cost per onboarding session | "Beyond the Context Window" |
| **Messages/turns** | Кол-во сообщений до понимания | MemoryAgentBench |
| **Time (sec)** | Стена-время от старта до первого правильного ответа | Наш вклад |
| **Accuracy (%)** | % правильных ответов после onboarding | Context-Bench |
| **Cost-performance ratio** | Accuracy / Cost | Letta leaderboard |
| **Token waste %** | % токенов на orientation vs understanding | Industry research |

### Протокол

1. **Новый диалог** для каждого подхода (чистый context window)
2. **Системный промпт**: "Ты AI-ассистент. Восстанови контекст проекта Bean & Brew через [источник]. Потом ответь на 5 вопросов."
3. **Phase 1 — Onboarding**: AI читает контекст из указанного источника
   - Для MD: читает файлы из `docs/`
   - Для Mem0: вызывает `search_memory` / `list_memories`
   - Для Helixir: вызывает `search_memory` + `search_reasoning_chain`
   - Замеряем: токены, время, кол-во tool calls
4. **Phase 2 — Verification**: 5 стандартных вопросов (те же для всех подходов)
   - Q1: "Какая архитектура проекта? Перечисли слои."
   - Q2: "Почему выбрали SQLite, а не PostgreSQL?"
   - Q3: "Какой тест flaky и почему?"
   - Q4: "Сколько всего тестов и как они распределены по слоям?"
   - Q5: "Что сломается если изменить схему миграций?"
5. **Оценка**: LLM-as-Judge (GLM 4.7) по 4 критериям, 1-4 шкала

### Формат демо на конференции

**Split-screen live comparison ("bake-off")**:

```
┌─────────────────┬─────────────────┬─────────────────┐
│   MD-файлы      │   Helixir MCP   │   Mem0          │
│                 │                 │                 │
│ tokens: 15,420  │ tokens: 8,200   │ tokens: 4,100   │
│ time: 3.2s      │ time: 5.1s      │ time: 2.8s      │
│ accuracy: 80%   │ accuracy: 95%   │ accuracy: 85%   │
│ cost: $0.015    │ cost: $0.008    │ cost: $0.004    │
│ ratio: 53.3     │ ratio: 118.8    │ ratio: 212.5    │
└─────────────────┴─────────────────┴─────────────────┘
```

Показываем:
1. **Вживую** — AI читает контекст из каждого источника (токен-счётчик тикает)
2. **Вопросы** — одинаковые 5 вопросов каждому
3. **Дашборд** — итоговая таблица cost/accuracy/time

### Предзаписанная часть vs живая

- **Pre-recorded**: onboarding phase (долгая, скучная для аудитории)
- **Live**: verification questions (интерактивная, драматичная)
- **Dashboard**: автоматически обновляется в реальном времени

## Методология подсчёта

### Почему двухфазный протокол

Основной бенчмарк (Parts A+B+C) подаёт контекст на вход и измеряет только **качество ответов**.
Но в реальности AI-агент сначала **добывает** контекст, а потом отвечает. Стоимость добычи
может отличаться на порядок между подходами. Context Recovery разделяет эти фазы:

- **Phase 1 (Onboarding)**: агент получает контекст из источника. Метрики: объём контекста
  (chars/tokens), время retrieval, количество tool calls.
- **Phase 2 (Verification)**: агент отвечает на 5 вопросов с полученным контекстом.
  Метрики: accuracy (LLM-as-Judge), input/output tokens, latency.

Разделение позволяет отдельно видеть: (a) сколько стоит получить контекст, (b) насколько
этот контекст полезен для ответов.

### Формулы метрик

**Token count:**
- Input tokens = context_tokens + sum(prompt_tokens для каждого вопроса)
- Output tokens = sum(completion_tokens для каждого ответа)
- Total tokens = input + output
- Для Cerebras API: берём `usage.prompt_tokens` и `usage.completion_tokens` из ответа
- Для MCP retrieval: оцениваем `len(text) / 4` (≈4 chars/token для смешанного ru/en)

**Cost estimate:**
- `cost = (input_tokens × $0.60 + output_tokens × $0.60) / 1,000,000`
- Цена Cerebras на момент бенчмарка: $0.60/M tokens (input = output)
- Это нижняя оценка: реальные LLM (Claude, GPT-4) стоят 10-50× дороже,
  но пропорции между подходами сохраняются

**Cost-Performance Ratio:**
- `CPR = median_score / cost_estimate`
- Выше = лучше (больше качества на доллар)
- Из [Letta Context-Bench](https://context-bench.com): они используют аналогичную метрику

**Accuracy:**
- `accuracy_pct = median_total_score / max_possible_score × 100`
- Max = 80 (5 вопросов × 4 критерия × 4 max балла)
- 3 прогона, берём медиану (устойчивость к outlier'ам)

### Как считаем токены для каждого подхода

| Подход | Onboarding | Что входит в context_tokens |
|--------|-----------|----------------------------|
| MD-файлы | Читаем `test_context.json` | Полный текст всех эпизодов (~20K chars) |
| GitHub Issues | Те же данные, формат issues | Текст + issue-разметка (~21K chars) |
| Mem0 | 5 semantic search + list_all | Только возвращённые результаты (variable) |
| Helixir MCP | 5×3 tools (memory+chain+concept) | Результаты всех MCP-вызовов (variable) |
| Graphiti | Те же данные, graph-формат | Текст с node-разметкой (~20K chars) |

**Ключевое различие**: MD/Issues/Graphiti передают **весь** контекст (~5K tokens).
Mem0 и Helixir передают **только релевантные** фрагменты. Это основной trade-off:
полнота vs компактность.

### Почему именно эти 5 вопросов

Вопросы покрывают разные типы знания:

| # | Тип знания | Что проверяет |
|---|-----------|--------------|
| Q1 | Структурное | Понимание архитектуры (факты из контекста) |
| Q2 | Каузальное | Причина решения (WHY, не WHAT) |
| Q3 | Аналитическое | Диагностика проблемы + trade-off analysis |
| Q4 | Количественное | Точные числа, распределение по слоям |
| Q5 | Impact analysis | Цепочка зависимостей, предсказание последствий |

Q2 и Q3 особенно интересны: каузальный граф (Helixir) должен давать преимущество
на вопросах "почему", тогда как плоский текст (MD) лучше на количественных вопросах.

### Оценка: LLM-as-Judge

- Evaluator: `zai-glm-4.7` (reasoning model, Cerebras)
- Generator ≠ Evaluator (устраняет circular bias, см. [основной бенчмарк](12_benchmark_design.md))
- 4 критерия: Accuracy, Completeness, Context Utilization, Specificity
- Шкала 1-4 (лучше дискриминирует чем 1-5, см. исследования в 12_benchmark_design.md)
- Для каждого подхода: 3 прогона → медиана (робастность)

### Ограничения

1. **Cerebras pricing не репрезентативен**: $0.60/M vs Claude $15/M input. Абсолютные
   цифры cost нужно масштабировать для реальных LLM. Но **пропорции** между подходами валидны.
2. **Mem0/Helixir зависят от качества ingestion**: если данные плохо загружены,
   retrieval вернёт мало. Это не баг бенчмарка — это часть стоимости подхода.
3. **GitHub Issues и Graphiti — симуляции**: мы форматируем те же данные по-другому,
   а не используем реальный GitHub API / Graphiti server. Для честного сравнения
   нужен реальный инфра (TODO для v2).
4. **5 вопросов — малая выборка**: для статистической значимости нужно 20+.
   Но для конференционного демо 5 достаточно.

## Реализация

### Скрипт бенчмарка

`benchmark/scripts/benchmark_context_recovery.py`:

```
python3 benchmark_context_recovery.py <approach|all> [context_file] [num_runs]

# Один подход:
CEREBRAS_API_KEY=... python3 benchmark_context_recovery.py helixir_mcp

# Все подходы:
CEREBRAS_API_KEY=... python3 benchmark_context_recovery.py all
```

Для Mem0 и Helixir MCP требуются запущенные серверы:
- Mem0: `docker compose up` в `infra/mem0-local/` (порт 8888)
- Helixir: HelixDB на порту 6970 + `helixir-mcp` бинарник
- Ollama: для embeddings (`nomic-embed-text`)

### Визуализация

`scripts/dashboard_recovery.html` — веб-дашборд для конференции:
- Split-screen карточки с token-счётчиками для каждого подхода
- Accuracy-бары с цветовой индикацией (green ≥85%, yellow ≥70%, red <70%)
- Сравнительная таблица всех метрик
- Загружает реальные результаты из `benchmark/results/recovery_comparison.json`
- Fallback на sample data для preview

### Выходные файлы

```
benchmark/results/
  recovery_md_files.json       # Детальные результаты по подходу
  recovery_github_issues.json
  recovery_mem0.json
  recovery_helixir_mcp.json
  recovery_graphiti.json
  recovery_comparison.json     # Сводная таблица для дашборда
```

## Связь с основным бенчмарком

Context Recovery — это **дополнение** к основному бенчмарку (Parts A+B+C):

| | Основной бенчмарк | Context Recovery |
|-|-------------------|-----------------|
| **Что измеряет** | Качество ответов | Стоимость получения контекста |
| **Контекст** | Подаётся на вход заранее | AI сам добывает из источника |
| **Архитектура** | LLM-as-Generator + Judge | LLM-as-Agent + token counting |
| **Формат** | Статический benchmark | Динамическое демо |
| **Метрики** | Score (accuracy) | Cost × Quality = Value |

Вместе они дают полную картину:

```
Value(подход) = Quality(основной бенчмарк) × Efficiency(context recovery)
             = (score / max_score) × (accuracy / cost)
```

Это позволяет ответить на вопрос: **какой подход даёт максимум пользы на вложенный доллар?**
