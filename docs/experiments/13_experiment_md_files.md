# Эксперимент 1: Управление тестовым контекстом через MD-файлы

**Ссылки и источники:**
- Cursor Rules: https://docs.cursor.com/context/rules-for-ai
- Cursor Best Practices (Lee Robinson, Jan 2026): https://cursor.com/blog
- Traycer AGENTS.md: https://docs.traycer.ai/tasks/agents-md
- BMAD-METHOD: https://github.com/bmadcode/BMAD-METHOD
- arXiv:2602.11988 (Context Files for Code Generation): https://arxiv.org/abs/2602.11988
- arXiv:2512.18925 (Spec-Driven Development): https://arxiv.org/abs/2512.18925
- arXiv:2307.03172 (Lost in the Middle): https://arxiv.org/abs/2307.03172
- Chroma «Context Rot» (исследование): https://research.trychroma.com/context-rot
- JetBrains AI research: https://blog.jetbrains.com/ai/

## Настройка

### Созданные файлы
- `AGENTS.md` — общий контекст проекта (архитектура, API, тестирование, конвенции)
- `.cursor/rules/testing.mdc` — правила для AI при работе с тестами (именование, структура, антипаттерны)
- `.cursor/rules/architecture.mdc` — правила архитектуры (слои, зависимости, как добавить новую сущность)
- `docs/test-index.md` — каталог всех 62 тестов с типом, покрытием, зависимостями
- `docs/test-patterns.md` — паттерны и антипаттерны тестирования с примерами кода
- `docs/test-context.md` — доменный контекст (сущности, поля, валидация, бизнес-логика)

### Общий объём контекста
~500 строк / ~4000 токенов в MD-файлах. Это умещается в context window при прямом включении.

## Наблюдения

### Плюсы
1. **Zero-cost setup** — файлы создаются один раз, не требуют инфраструктуры
2. **Version control** — изменения контекста видны в git diff
3. **Человекочитаемость** — любой разработчик может прочитать и понять
4. **Cursor auto-attach** — .cursor/rules автоматически включаются в промпт при matching по globs
5. **Структурируемость** — можно разделить контекст по доменам (тесты, архитектура, домен)

### Минусы
1. **Ручное обновление** — при изменении кода MD-файлы устаревают (context rot)
2. **Нет семантического поиска** — AI видит весь файл, но не может query по конкретному тесту
3. **Масштабируемость** — при 500+ тестах test-index.md станет огромным
4. **Дубли** — AI склонен копировать контент из docs в ответы, а потом снова в docs при обновлении
5. **Нет каузальных связей** — файлы не знают почему тест был изменён
6. **Context window pressure** — всё включается целиком, даже если нужна одна строка

## Ссылки на исследования

### Подтверждающие проблемы
- **"Beyond the Prompt: An Empirical Study of Cursor Rules"** (arXiv:2512.18925, 2025)
  - Анализ 200+ cursor rules: самая частая категория — Quality Assurance (тестирование)
  - "Many cursor rules include very high-level programming best practices, such as separation of concerns, modularity"
  - Проблема: правила часто повторяют то, что опытный разработчик и так знает

- **"Evaluating AGENTS.md"** (arXiv:2602.11988, 2026)
  - Эмпирическая оценка context files для Claude Code, Codex, Qwen Code
  - 60,000+ публичных репозиториев уже содержат context files
  - "Claude Code prompt advocates for a high-level overview only and warns against listing components that are easily discoverable"
  - Вывод: **AGENTS.md помогает, но не решает проблему масштабного контекста**

- **"The Complexity Trap"** (JetBrains, NeurIPS 2025 DL4Code Workshop)
  - LLM-based summarisation работает не лучше простого observation masking
  - "Simple observation masking is as efficient as LLM summarization for agent context management"
  - Вывод: **сложные стратегии сжатия контекста не оправдывают себя**

- **"Context Rot"** (Chroma Research, 2025)
  - Увеличение input tokens снижает качество ответов LLM
  - Модели теряют информацию из середины длинного контекста ("Lost in the Middle", arXiv:2307.03172)

- **"When Coding Agents Forget"** (Smart Articles, 2025)
  - AI task duration doubles every 7 months → context management всё важнее
  - Иерархия памяти: working memory → episodic memory → semantic memory

### Подтверждающие подход
- **Cursor Best Practices** (cursor.com/blog, Lee Robinson, Jan 2026)
  - "Reference files instead of copying their contents"
  - "Keep rules focused on essentials: commands, patterns, pointers to canonical examples"
  - Правило 100 строк: если файл правил > 100 строк, его нужно разбить

- **Traycer AGENTS.md** (docs.traycer.ai)
  - Структурированный подход к контекст-файлам для AI-агентов
  - Разделение на: overview, architecture, conventions, known issues

## Результаты бенчмарка

### Benchmark v2 — Part A (12 сценариев, шкала 1-4, отдельный evaluator)

> **Generator**: gpt-oss-120b | **Evaluator**: zai-glm-4.7 (GLM 4.7 MoE 358B/32B active)
> **Тесты**: 175 функций (241 с подтестами) | **Контекст**: 21 эпизод, ~20K chars
> **3 прогона**, медианы по сценариям

**Median: 123/192 (64.1%)** | Mean: 123.67 ± 2.08 | Range: 122–126

| Сценарий | Median | Runs | Комментарий |
|----------|--------|------|-------------|
| S1: Генерация теста | 0/16 | [0, 15, 0] | Высокая дисперсия — генерация кода наиболее стохастична |
| S2: Покрытие endpoint | 11/16 | [9, 11, 12] | Стабильно среднее — test-index.md содержит маппинг |
| S3: Flaky анализ | 13/16 | [16, 0, 13] | Описания достаточно, но иногда полный провал |
| S4: Рефакторинг | 9/16 | [8, 11, 9] | architecture.mdc описывает связи слоёв |
| S5: E2E тест | 16/16 | [14, 16, 16] | **Лучший сценарий** — test-patterns.md даёт хорошую базу |
| S6: Impact analysis | 13/16 | [9, 13, 15] | Улучшение vs v1 благодаря расширенному контексту |
| S7: Обнаружение дублей | 4/16 | [4, 4, 4] | Ceiling effect — недостаточно контекста без спец. инструментов |
| S8: Test plan | 13/16 | [16, 13, 12] | Стабильно хорошо |
| S9: Темпоральный | 4/16 | [5, 4, 4] | MD-файлы не хранят историю |
| S10: Оптимизация | 14/16 | [15, 14, 14] | Стабильно высокий результат |
| S11: Coverage matrix | 9/16 | [11, 9, 7] | Средне — нет семантической группировки |
| S12: Dependencies | 16/16 | [16, 16, 16] | **Идеальный** — все прогоны дали max |

**Ключевое наблюдение v2:** MD-файлы показали **минимальную дисперсию** (σ=2.08) среди всех подходов.
Все 3 прогона дали 122–126 баллов. Предсказуемость — главное преимущество: весь контекст подаётся
identically каждый раз, нет стохастичности от retrieval.

---

### Benchmark v1 — Part A (10 сценариев, шкала 0-5, self-evaluation)

**Part A: 145/250 (58.0%)**

| Сценарий | Оценка | Комментарий |
|----------|--------|-------------|
| S1: Генерация теста | 20/25 | Видит существующие тесты через test-index.md |
| S2: Поиск покрытия | 14/25 | test-index.md содержит маппинг, но неполный |
| S3: Flaky анализ | 23/25 | Нет каузальных связей, но описания достаточно |
| S4: Рефакторинг | 9/25 | architecture.mdc описывает связи слоёв |
| S5: E2E тест | 23/25 | Видит паттерны в test-patterns.md |
| S6: Impact analysis | 6/25 | Нет связей schema↔test |
| S7: Обнаружение дублей | 8/25 | Зависит от длины test-index.md |
| S8: Test plan | 20/25 | architecture.mdc описывает процесс добавления |
| S9: Темпоральный контекст | 4/25 | MD-файлы не хранят историю |
| S10: Оптимизация suite | 18/25 | test-patterns.md подсказывает, но нет полной картины |

**Part B: 78/125 (62.4%)** | **Part C: 121/125 (96.8%)** | **Итого: 344/500 (68.8%)**

## Обновления после бенчмарка (2026-04-14)

### Масштабирование
Проект масштабирован с 62 до **336 тестовых функций** (~637 прогонов в `go test -v`).

### Текущий состав файлов
- `AGENTS.md` — обзор проекта, архитектура, API, тестирование
- `.cursor/rules/architecture.mdc` — архитектура (на русском)
- `.cursor/rules/testing.mdc` — правила тестирования (на русском)
- `.cursor/rules/github.mdc` — работа с Issues: staleness detection, чекбоксы, закрытие (на русском)
- `.cursor/rules/mem0.mdc` — правила работы с Mem0 MCP (на русском)
- `.cursor/rules/helixir.mdc` — правила работы с Helixir MCP (на русском)
- `docs/test-index.md` — индекс всех тестов
- `docs/test-context.md` — доменная область и среда
- `docs/test-patterns.md` — паттерны и антипаттерны
- `docs/known_issues.md` — **новый**: flaky тесты, баги, пробелы покрытия
- `prompts/` — **новый**: 4 промта онбординга (MD, Issues, Mem0, Helixir)

### Стоимость обслуживания (Phase 2)
Обновление MD-файлов после масштабирования потребовало:
- Ручное обновление чисел (62→336) во всех файлах
- Добавление дат актуальности в заголовки
- Перевод всех файлов на русский (язык команды)
- Создание нового файла known_issues.md
- Уточнение формулировки «337 sub-tests» → «637 прогонов в go test -v»

**Ключевое наблюдение:** обновление MD — полностью ручной процесс. Агент не обновляет файлы самостоятельно (в отличие от Issues, где может добавить комментарий).

### Практическая верификация (Cursor, 2026-04-14)
Онбординг через MD-промт дал корректные результаты: все данные совпали с реальностью, 336/637 объяснены правильно, coverage верифицировано. Инфра-проблем 0. Самый надёжный подход при актуальных данных.

## Выводы

MD-файлы — это **baseline** подход. Он работает для проектов с <100 тестами и стабильной
кодовой базой. Основные ограничения:
1. Не масштабируется (context window)
2. Устаревает без ручного обновления
3. Не поддерживает темпоральные запросы
4. Не поддерживает каузальный анализ

**Обновление после Phase 2:** при актуальных данных MD — самый надёжный и дешёвый подход.
Но стоимость поддержания актуальности — полностью на людях. Это скрытый OPEX.

Это подтверждается исследованиями: arXiv:2602.11988 показывает что context files помогают,
но их эффект ограничен; JetBrains исследование показывает что даже сложные стратегии сжатия
не решают проблему полностью.
