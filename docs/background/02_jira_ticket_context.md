# Хранение контекста в виде Jira/тикетов — AI агент ведёт работу

## Обзор подхода

Идея: AI-агент не просто выполняет задачи, а **самостоятельно заполняет тикеты**, ведёт работу через комментарии, обновляет статусы и создаёт аудируемый след своей деятельности в системе управления проектами.

## Кто так делает?

### 1. Atlassian — Agents in Jira (Open Beta, 2026)
- Агенты появляются как **assignee** в Jira с теми же полями и паттернами
- Можно @mention агентов в комментариях для in-context взаимодействия
- Jira отслеживает все действия агентов — они становятся **accountable members of the team**
- Rovo Agent (Service Request Helper) — анализирует тикеты, рекомендует действия
- **Источник**: [atlassian.com/blog/announcements/ai-agents-in-jira](https://www.atlassian.com/blog/announcements/ai-agents-in-jira)

### 2. Linear — AI agents в product development
- Агенты (Codex, Cursor, GitHub Copilot) интегрированы в issue tracker
- Структурные диффы для human и agent output
- **Источник**: [linear.app](https://linear.app/)

### 3. Helios (AGENTS.md + autonomous PRs)
- Каждая роль владеет конкретными файлами
- Planning в `.sys/plans/{role}/` как письменные контракты
- 1800+ автономных PR, 90% — без участия человека
- **Источник**: HN discussion, 2026

### 4. SWE-Agent (Princeton)
- Берёт GitHub issue и автоматически пытается починить
- Создаёт branch, пишет код, открывает PR
- **Источник**: [github.com/princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent)

### 5. Traycer — Ticket Assist
- AI заполняет тикеты из conversation context
- Генерирует tasks из спецификаций
- **Источник**: [docs.traycer.ai](https://docs.traycer.ai)

### 6. BridgeApp — Work OS для hybrid human-AI teams
- Нативный AI-agent framework для работы с тасками, чатами, документами
- Агенты оперируют прямо в task tracker
- **Источник**: [bridgeapp.ai](https://bridgeapp.ai)

## Исследования

| Исследование | Суть |
|-------------|------|
| Gartner (2026) | 50% IT service desks развернут AI-powered virtual agents к 2026 |
| CIO (2026) "Taming AI agents" | Оркестратор делегирует Jira-агенту pull тикетов — микросервисная архитектура агентов |
| Stack Overflow Research (2026) | Сканирование 470 GitHub repos — AI генерирует специфические категории багов |
| VoltAgent/awesome-ai-agent-papers | Обширная коллекция research papers по автономным агентам |

## Является ли это антипаттерном?

### Аргументы ЗА (это НЕ антипаттерн):
1. **Аудируемость** — полный след решений и действий агента
2. **Контроль** — человек видит что агент делает в реальном времени
3. **Интеграция** — работает с существующими процессами команды
4. **Accountability** — агент как ответственный член команды
5. **Масштабируемость** — множество агентов, каждый со своей зоной ответственности
6. **Историчность** — контекст сохраняется в хронологическом порядке

### Аргументы ПРОТИВ (потенциальный антипаттерн):
1. **"Jira becomes the job"** — обновление тикетов превращается в отдельный workstream
2. **Риск галлюцинаций** — агент может удалить все тикеты (Murphy's Law of AI hallucination)
3. **Шум** — комментарии агента могут засорять тикет
4. **Lock-in** — зависимость от конкретного трекера
5. **Overhead** — дополнительные токены на формирование структурированных обновлений
6. **False sense of progress** — много обновлений ≠ реальный прогресс

### Рекомендации из индустрии:
> "Forget controlling the agents themselves; control their tools instead. If a tool has the ability to delete all JIRA tickets — it eventually will happen."
> — CIO, "Taming AI agents", 2026

> "Most agent work today happens in one-off chats that never make it back to where the work lives and is coordinated."
> — Atlassian, 2026

## Плюсы подхода

- Структурированный аудит всех действий агента
- Интеграция в существующие workflow команды
- Человек в контуре через review комментариев
- Хронологический контекст с привязкой к задачам
- Возможность вернуться к любой точке принятия решения
- Естественная граница ответственности (scope тикета)

## Минусы подхода

- Высокий overhead на формирование обновлений
- Риск "бюрократизации" — tracker becomes the job
- Нет семантического поиска по истории (только текстовый)
- Ограниченная связность между тикетами (нет графа знаний)
- Зависимость от конкретной платформы (Jira/Linear/GitHub)
- Нет механизма забывания — информация только накапливается
