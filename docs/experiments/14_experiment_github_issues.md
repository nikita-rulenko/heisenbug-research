# Эксперимент 2: Управление тестовым контекстом через GitHub Issues MCP

## Настройка

### Репозиторий
https://github.com/nikita-rulenko/heisenbug-coffee-portal

### Созданные Issues
Через GitHub MCP (`create_issue`) создано 9 issues:

| # | Тема | Labels |
|---|------|--------|
| 1 | Product entity unit tests | test:unit, context:coverage |
| 2 | Order entity unit tests | test:unit, context:coverage |
| 3 | NewsItem and Category unit tests | test:unit, context:coverage |
| 4 | Product repository integration tests | test:integration, context:coverage |
| 5 | Order repository integration tests | test:integration, context:coverage |
| 6 | HTTP API tests | test:api, context:coverage |
| 7 | UseCase business logic tests | test:usecase, context:coverage |
| 8 | Architecture: Clean Architecture layers | context:domain |
| 9 | Test Patterns: helpers and isolation | context:pattern |

### Структура Labels
- `test:unit`, `test:integration`, `test:api`, `test:usecase`, `test:e2e` — тип теста
- `test:flaky` — потенциально нестабильные тесты
- `context:coverage` — информация о покрытии
- `context:pattern` — паттерны тестирования
- `context:domain` — доменный контекст

## Наблюдения

### Плюсы
1. **Структурированность** — labels позволяют фильтровать контекст (search_issues по label)
2. **Аудит и история** — каждое изменение issue фиксируется с timestamp
3. **Collaboration** — можно назначить ответственных, добавить комментарии
4. **Cross-reference** — issues могут ссылаться друг на друга (#1 depends on #8)
5. **GitHub MCP** — AI-агент может искать и создавать issues через search_issues
6. **Free** — GitHub Issues бесплатны для public repos

### Минусы
1. **Overhead на создание** — каждый issue требует осмысленного описания
2. **Нет семантического поиска** — search_issues ищет по тексту, не по смыслу
3. **Нет графа зависимостей** — cross-references через mentions, не через формальные связи
4. **Token cost** — issue body может быть длинным, весь JSON ответ тяжёлый
5. **Network dependency** — каждый запрос к GitHub API, возможны таймауты (наблюдали)
6. **Разрозненность** — контекст размазан по 9+ issues vs 3 файла в MD-подходе
7. **Нет темпоральных запросов** — "что изменилось с прошлой недели" невозможно

## Сравнение с MD-файлами

| Критерий | MD-файлы | GitHub Issues |
|----------|----------|--------------|
| Setup cost | Минимальный | Средний (issues, labels) |
| Retrieval | Весь файл целиком | По label/query |
| Обновление | Ручное редактирование | Issue update, комментарии |
| История | git log | Issue timeline |
| Масштабируемость | Плохо (context window) | Лучше (фильтрация) |
| Offline | Работает | Нет (GitHub API) |
| Каузальность | Нет | Нет |
| Семантика | Нет | Нет |

## Результаты бенчмарка

### Benchmark v2 — Part A (12 сценариев, шкала 1-4, отдельный evaluator)

> **Generator**: gpt-oss-120b | **Evaluator**: zai-glm-4.7 (GLM 4.7 MoE 358B/32B active)
> **Тесты**: 175 функций (241 с подтестами) | **Контекст**: 21 эпизод, ~20K chars
> **3 прогона**, медианы по сценариям

**Median: 122/192 (63.5%)** | Mean: 119.67 ± 12.66 | Range: 106–131

| Сценарий | Median | Runs | Комментарий |
|----------|--------|------|-------------|
| S1: Генерация теста | 12/16 | [12, 13, 0] | Лучше MD (0) — issues содержат конкретные примеры тестов |
| S2: Покрытие endpoint | 11/16 | [13, 9, 11] | На уровне MD — label-фильтрация не даёт преимущества |
| S3: Flaky анализ | 10/16 | [10, 10, 13] | Ниже MD — issue формат фрагментирует контекст |
| S4: Рефакторинг | 7/16 | [9, 7, 6] | Слабо — issue #8 описывает архитектуру, но неполно |
| S5: E2E тест | 16/16 | [16, 16, 16] | **Идеально стабильный** — все 3 прогона max |
| S6: Impact analysis | 9/16 | [9, 11, 8] | Нет структурных связей schema↔test |
| S7: Обнаружение дублей | 4/16 | [4, 4, 9] | Ceiling effect (один выброс в run 3) |
| S8: Test plan | 13/16 | [13, 15, 13] | Стабильно — issue #8 + #9 |
| S9: Темпоральный | 4/16 | [4, 4, 4] | Полный провал — issue timeline не помогает |
| S10: Оптимизация | 14/16 | [14, 14, 14] | **Идеально стабильный** |
| S11: Coverage matrix | 11/16 | [11, 7, 12] | Чуть лучше MD благодаря label-структуре |
| S12: Dependencies | 12/16 | [16, 12, 0] | Высокая дисперсия — от 0 до 16 |

**Ключевое наблюдение v2:** GH Issues показали **высокую дисперсию** (σ=12.66) — самую большую
после Helixir. Разброс 106–131 за 3 прогона. Причина: фрагментация контекста по 9+ issues
создаёт нестабильность в том, как LLM агрегирует информацию из разных источников.

---

### Benchmark v1 — Part A (10 сценариев, шкала 0-5, self-evaluation)

**Part A: 146/250 (58.4%)**

| Сценарий | Оценка | Комментарий |
|----------|--------|-------------|
| S1: Генерация теста | 25/25 | Issue с существующими тестами найден |
| S2: Поиск покрытия | 7/25 | search_issues по label неполный |
| S3: Flaky анализ | 23/25 | Issue #4 с пометкой о flakiness |
| S4: Рефакторинг | 13/25 | Issue #8 описывает архитектуру |
| S5: E2E тест | 18/25 | Issue #9 описывает паттерны, но фрагментарно |
| S6: Impact analysis | 8/25 | Нет связей schema↔test в issues |
| S7: Обнаружение дублей | 6/25 | Нужно читать несколько issues и сравнивать |
| S8: Test plan | 25/25 | Issue #8 + #9 дают хорошую базу |
| S9: Темпоральный контекст | 0/25 | Issue timeline не помогает без семантики |
| S10: Оптимизация suite | 21/25 | Контекст достаточен |

**Part B: 85/125 (68.0%)** | **Part C: 117/125 (93.6%)** | **Итого: 348/500 (69.6%)**

## Обновления после бенчмарка (2026-04-14)

### Масштабирование Issues
Проект масштабирован до 336 тестовых функций (~637 прогонов). Issues расширены:

| # | Тема | Статус | Labels |
|---|------|--------|--------|
| 1-7 | Test coverage (entity, repository, handler, usecase) | **CLOSED** | test:*, context:coverage |
| 8 | Architecture documentation | OPEN (living doc) | context:domain |
| 9 | Test patterns documentation | OPEN (living doc) | context:pattern |
| 10 | **Handler coverage 67%→80%+** | OPEN | context:coverage |
| 11 | **t.Parallel() для unit тестов** | OPEN | — |
| 12 | **E2E browser тесты** | OPEN | — |
| 13 | **Repository coverage 77.5%→85%+** | OPEN | context:coverage |
| 14 | **Общий анализ и roadmap** | OPEN | — |

### Новые правила для агента (.cursor/rules/github.mdc)
Добавлены 3 ключевых блока:
1. **Staleness detection** — агент проверяет даты в MD и комментариях Issues (порог 7/14 дней)
2. **Чекбоксы** — агент отмечает `- [x]` при выполнении, это ключевое преимущество Issues перед MD
3. **Auto-close** — агент закрывает тикет когда все AC выполнены, с итоговым комментарием

### Стоимость обслуживания (Phase 2)
В отличие от MD, обновление Issues происходит **по ходу работы**: агент добавляет комменты, отмечает чекбоксы, закрывает тикеты. Создание 5 новых тикетов (#10-#14) с acceptance criteria и чекбоксами потребовало одну команду `gh issue create` на каждый.

**Ключевое наблюдение:** Issues — единственный подход, где обновления **видны команде** (не только следующему AI-агенту). Комментарий в #14 виден всем, в отличие от обновления записи в Mem0/Helixir.

### Практическая верификация (Cursor, 2026-04-14)
Онбординг через Issues-промт: корректные результаты, агент добавил комментарий в #14 (двусторонняя связь), правильно идентифицировал living docs (#8, #9) и не пытался их закрыть. Одна инфра-проблема: GraphQL таймаут при первом вызове `gh issue view`.

Побочный эффект: агент попытался вызвать Helixir MCP, хотя промт этого не требовал. Исправлено добавлением явного ограничения «используй ТОЛЬКО этот подход» в промт.

## Ссылки

- GitHub Copilot Coding Agent (Issues-based workflow): https://github.blog/changelog/2025-05-19-github-copilot-coding-agent-in-public-preview/
- arXiv:2602.11988 — Evaluating AGENTS.md (context files for coding agents)
- Atlassian Jira agents: https://www.atlassian.com/blog/announcements/ai-agents-in-jira
- Linear (AI-native issue tracker): https://linear.app
- SWE-Agent (Princeton, issue→PR): https://github.com/princeton-nlp/SWE-agent
