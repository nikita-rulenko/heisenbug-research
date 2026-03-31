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

## Реализация

### Скрипт бенчмарка

Нужен Python-скрипт, который:
1. Запускает MCP-клиент для каждого подхода
2. Отправляет onboarding prompt
3. Считает токены (через Cerebras API usage field)
4. Отправляет 5 verification questions
5. Оценивает через GLM 4.7
6. Собирает метрики в JSON

### Визуализация

Веб-дашборд (HTML + JS) для конференции:
- Реал-тайм токен-счётчик
- Прогресс-бар onboarding
- Таблица результатов
- Графики cost vs accuracy

## Связь с основным бенчмарком

Context Recovery — это **дополнение** к основному бенчмарку (Parts A+B+C):

| Основной бенчмарк | Context Recovery |
|-------------------|-----------------|
| Измеряет **качество** ответов | Измеряет **стоимость** получения контекста |
| Все подходы получают контекст заранее | AI сам восстанавливает контекст |
| LLM-as-Generator + LLM-as-Judge | LLM-as-Agent + token counting |
| Статический benchmark | Динамическое демо |

Вместе они дают полную картину: **cost × quality = value** каждого подхода.
