# Spec-Driven Development и хранение контекста в MD файлах

## Обзор подхода

**Spec-Driven Development (SDD)** — методология, в которой основным артефактом является не код, а спецификация в формате Markdown. AI-агенты генерируют или регенерируют код из этой спецификации. Код становится одноразовым, спецификация — системой записи (system of record).

> "Spec-driven development flips the model: intent is made explicit, constraints are written down, decisions are recorded, agents operate inside defined boundaries."
> — Addy Osmani, LinkedIn 2026

## Ключевые форматы хранения контекста

### AGENTS.md
- **Статус**: де-факто стандарт для AI-ассистентов (2025-2026)
- **Поддержка**: Cursor, GitHub Copilot, Factory, Codex, Jules, Traycer и др.
- **Суть**: Markdown-файл с инструкциями для AI-агентов — build-процессы, тестирование, конвенции, архитектурные паттерны
- **Источник**: [docs.traycer.ai/tasks/agents-md](https://docs.traycer.ai/tasks/agents-md)

### .cursor/rules/*.mdc
- **Статус**: нативный формат Cursor IDE
- **Суть**: Markdown-файлы с метаданными, scoped по путям, версионируемые
- **Источник**: [cursor.com/docs/rules](https://cursor.com/docs/rules)

### Spec Kit (GitHub)
- **Статус**: официальный инструмент Microsoft/GitHub для SDD
- **Структура**: `specs/` → `plan.md` → `tasks.md` → код
- **Источник**: [developer.microsoft.com/blog/spec-driven-development-spec-kit](https://developer.microsoft.com/blog/spec-driven-development-spec-kit)

### BMAD-METHOD
- **Статус**: open-source фреймворк с 12+ ролевыми агентами
- **Суть**: IDE-agnostic, тяжёлый enterprise planning

## Ключевые исследования и источники

| Источник | Год | Суть |
|----------|-----|------|
| [GitHub Blog: Spec-driven development](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-using-markdown-as-a-programming-language-when-building-with-ai/) | 2025 | Markdown как язык программирования, Copilot компилирует в Go |
| [Addy Osmani: How to write a good spec](https://addyosmani.com/blog/good-spec/) | 2025 | Принципы написания спеков, антипаттерны, исследование GitHub 2500+ agent-файлов |
| [Martin Fowler: SDD Tools](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) | 2026 | Критический анализ Kiro, spec-kit, Tessl |
| [JetBrains: Spec-Driven Approach](https://blog.jetbrains.com/junie/2025/10/how-to-use-a-spec-driven-approach-for-coding-with-ai/) | 2025 | Практическое руководство по SDD с Junie |
| [Arun Gupta: Spec-driven Development (video)](https://www.youtube.com/watch?v=G2Yn1btfZrk) | 2026 | Мультиагентный SDD с AGENTS.md |
| [InfoQ: Reassessing AGENTS.md](https://www.infoq.com/news/2026/03/agents-context-file-value-review/) | 2026 | Переоценка ценности context-файлов |
| [Tessl: AGENTS.md isn't the problem](https://tessl.io/blog/your-agentsmd-file-isnt-the-problem-your-lack-of-evals-is/) | 2026 | Проблема не в файлах контекста, а в отсутствии evals |
| [Augment Code: 6 Best SDD Tools](https://www.augmentcode.com/tools/best-spec-driven-development-tools) | 2026 | Сравнение 6 инструментов SDD |

## Антипаттерны

### 1. Monolithic Mega-Prompt
Перегрузка одного агента сотнями инструкций. Liu et al. (2023) показали эффект "Lost in the Middle" — точность извлечения информации с позиции 10 из 20 документов падает до ~55% (с ~80% на позиции 1). arXiv:2307.03172.

### 2. Раздутые context-файлы
> "A 200-line AGENTS.md that the model ignores or misinterprets is worse than a 10-line file with three instructions the model reliably follows."
> — Tessl

### 3. Context window exhaustion
При ~50% заполнения контекстного окна начинаются галлюцинации. Решение — начинать новый чат, а не суммаризировать.

### 4. Устаревшие спецификации
Забывают обновлять `copilot-instructions.md` после изменений. Спек дрифтит от кода.

### 5. Агент игнорирует инструкции
Martin Fowler (2026): "I frequently saw the agent ultimately not follow all the instructions... just because the windows are larger, doesn't mean AI will properly pick up on everything."

### 6. Invisible State (anti-pattern)
Полагаться на LLM для запоминания состояния вместо явного управления стейтом.

### 7. Отсутствие evaluation
Невозможно измерить, работают ли context-файлы без eval-фреймворка. Нет baseline, нет метрик.

## Плюсы подхода

- Нулевое время онбординга для нового агента
- Контекст персистентен между сессиями
- Version-controlled, reviewable
- Низкий порог входа (plain Markdown)
- Переносимость между IDE и агентами
- Вынуждает артикулировать неявные знания о проекте

## Минусы подхода

- Статичен — не обновляется автоматически
- Нет семантического поиска — весь файл загружается в контекст
- Не масштабируется — больше 15-20 правил начинают конфликтовать
- Требует ручного поддержания актуальности
- Нет механизма забывания устаревшей информации
- Ограничен размером контекстного окна
