# Эксперимент 1: Управление тестовым контекстом через MD-файлы

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

## Оценка по бенчмарку (предварительная)

| Сценарий | Ожидаемая оценка | Комментарий |
|----------|-----------------|-------------|
| S1: Генерация теста | 20/25 | Видит существующие тесты через test-index.md |
| S2: Поиск покрытия | 22/25 | test-index.md содержит маппинг |
| S3: Flaky анализ | 15/25 | Нет каузальных связей, нет истории |
| S4: Рефакторинг | 18/25 | architecture.mdc описывает связи слоёв |
| S5: E2E тест | 17/25 | Видит паттерны в test-patterns.md |
| S6: Impact analysis | 14/25 | Нет связей schema↔test |
| S7: Обнаружение дублей | 16/25 | Зависит от длины test-index.md |
| S8: Test plan | 19/25 | architecture.mdc описывает процесс добавления |
| S9: Темпоральный контекст | 5/25 | MD-файлы не хранят историю |
| S10: Оптимизация suite | 17/25 | test-patterns.md подсказывает, но нет полной картины |
| **Итого (ожидание)** | **~163/250** | **~65%** |

## Выводы

MD-файлы — это **baseline** подход. Он работает для проектов с <100 тестами и стабильной
кодовой базой. Основные ограничения:
1. Не масштабируется (context window)
2. Устаревает без ручного обновления
3. Не поддерживает темпоральные запросы
4. Не поддерживает каузальный анализ

Это подтверждается исследованиями: arXiv:2602.11988 показывает что context files помогают,
но их эффект ограничен; JetBrains исследование показывает что даже сложные стратегии сжатия
не решают проблему полностью.
