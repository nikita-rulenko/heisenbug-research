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

## Оценка по бенчмарку (предварительная)

| Сценарий | Ожидаемая оценка | Комментарий |
|----------|-----------------|-------------|
| S1: Генерация теста | 18/25 | Может найти issue с существующими тестами |
| S2: Поиск покрытия | 20/25 | search_issues по label хорошо работает |
| S3: Flaky анализ | 14/25 | Может найти issue #4 с пометкой о flakiness |
| S4: Рефакторинг | 16/25 | Issue #8 описывает архитектуру |
| S5: E2E тест | 15/25 | Issue #9 описывает паттерны, но фрагментарно |
| S6: Impact analysis | 13/25 | Нет связей schema↔test в issues |
| S7: Обнаружение дублей | 14/25 | Нужно читать несколько issues и сравнивать |
| S8: Test plan | 17/25 | Issue #8 + #9 дают базу |
| S9: Темпоральный контекст | 8/25 | Issue timeline хранит историю, но нет семантики |
| S10: Оптимизация suite | 15/25 | Фрагментированный контекст |
| **Итого (ожидание)** | **~150/250** | **~60%** |

## Ссылки

- GitHub Copilot Coding Agent (Issues-based workflow): https://github.blog/changelog/2025-05-19-github-copilot-coding-agent-in-public-preview/
- arXiv:2602.11988 — Evaluating AGENTS.md (context files for coding agents)
- Atlassian Jira agents: https://www.atlassian.com/software/jira/ai-agents
- Linear (AI-native issue tracker): https://linear.app
- SWE-Agent (Princeton, issue→PR): https://github.com/princeton-nlp/SWE-agent
