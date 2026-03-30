# AI-агенты + GitHub Issues — бесплатные и open-source решения

## Обзор

GitHub Issues — полностью бесплатная система тикетов, встроенная в GitHub. В 2025-2026 экосистема агентов вокруг GitHub Issues **значительно богаче**, чем вокруг Jira. Несколько решений позволяют AI-агенту автономно работать с issues, создавать ветки, писать код и открывать PR.

---

## 1. GitHub Copilot Coding Agent (GitHub)

**Статус**: Production, самый зрелый  
**Цена**: GitHub Free (ограниченно) / $10/mo (Pro) / $19/mo (Team)

### Как работает
1. Создаёшь GitHub Issue с описанием задачи
2. Assignишь issue на `@copilot` (как на коллегу)
3. Агент ставит 👀 emoji и начинает работу в фоне
4. Загружает VM, клонирует репо, анализирует код через RAG + GitHub Code Search
5. Создаёт ветку, пишет код, коммитит, открывает draft PR
6. Обновляет описание PR по мере работы, пишет session logs
7. Реагирует на комментарии в PR для итераций

### Особенности
- Поддерживает MCP серверы для доступа к внешним данным
- Понимает изображения в issues (скриншоты багов, мокапы)
- Соблюдает branch protection rules
- Человек должен approve перед запуском CI/CD
- AGENTS.md определяет контекст проекта для агента

### CLI
```bash
gh agent-task create "Fix the authentication bug in login.ts"
gh agent-task create --base main --repo owner/repo --follow "Add unit tests"
```

**Источники**:
- [GitHub Blog: Meet the new coding agent](https://github.blog/news-insights/product-news/github-copilot-meet-the-new-coding-agent/)
- [GitHub Docs: Asking Copilot to create a PR](https://docs.github.com/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/create-a-pr)

---

## 2. Kiro Autonomous Agent (AWS)

**Статус**: Production  
**Цена**: Free tier available

### Как работает
1. В любом GitHub issue пишешь `/kiro <описание задачи>`
2. Или assignишь issue на `kiro`
3. Агент клонирует репо в изолированный sandbox
4. Создаёт feature branch, коммитит с co-author attribution
5. Открывает PR с детальным описанием, подходом и trade-offs
6. Реагирует на feedback через `/kiro all` (все комментарии) или `/kiro fix` (конкретный)

### Особенности
- Может работать с несколькими репозиториями в одной задаче
- Изолированный sandbox для каждой задачи
- Respects branch protection rules и org policies
- Только пользователь с write access может назначать задачи

**Источник**: [kiro.dev/docs/autonomous-agent/github](https://kiro.dev/docs/autonomous-agent/github/)

---

## 3. Claude Code + GitHub Actions (Anthropic)

**Статус**: Production  
**Цена**: API usage (pay per token)

### Как работает
1. Устанавливаешь GitHub App: `/install-github-app`
2. В любом PR или issue пишешь `@claude`
3. Claude анализирует изменения, предлагает улучшения
4. Может создавать PR и реализовывать фиксы в изолированных средах

### GitHub Action
```yaml
name: Claude Code Review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          model: claude-opus-4-5-20251101
```

**Источник**: [digitalapplied.com/blog/ai-code-review-automation-guide-2025](https://www.digitalapplied.com/blog/ai-code-review-automation-guide-2025)

---

## 4. SWE-Agent (Princeton, Open Source)

**Статус**: Research / Production-ready  
**Цена**: Бесплатно (open source) + LLM API costs  
**GitHub**: [github.com/princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent)

### Как работает
1. Берёт GitHub issue
2. Автоматически анализирует codebase
3. Создаёт патч для исправления
4. Открывает PR

### Особенности
- Полностью open-source
- Поддерживает GPT-4, Claude и другие модели
- Один из первых academic-grade autonomous coding agents
- SWE-bench результаты: top-tier на момент выхода

---

## 5. Aider + GitHub Actions (Open Source)

**Статус**: Production  
**Цена**: Бесплатно (open source) + LLM API costs (~$0.50 на 10 крупных изменений)  
**GitHub**: [github.com/paul-gauthier/aider](https://github.com/paul-gauthier/aider)

### Как работает
1. `aider-github-action` интегрируется с GitHub Actions
2. При создании issue — автоматически создаёт branch и PR
3. Работает с diff-ами, не генерирует целые файлы
4. Отправляет карту проекта в LLM для контекста

### Особенности
- Экстремально дёшево: GPT-4 Turbo ~$0.05 за сессию
- Работает с большими кодовыми базами
- Оптимизированные промпты и diff-based подход

---

## 6. CodeRabbit (AI Code Review)

**Статус**: Production  
**Цена**: Free (basic), Pro $24/mo

### Как работает
- Автоматически ревьюит каждый PR
- Оставляет line-by-line комментарии, генерирует саммари и диаграммы
- Отвечает на вопросы в PR threads
- Команды: `@coderabbitai` для генерации тестов, docs, issues
- Учится на thumbs up/down

**Источник**: [builder.io/blog/best-ai-tools-2026](https://www.builder.io/blog/best-ai-tools-2026)

---

## 7. Open-Source Issue Trackers с AI + GitHub интеграцией

### Plane (⭐ крупнейший open-source)
- **GitHub**: [github.com/makeplane/plane](https://github.com/makeplane/plane)
- **MCP Server**: [github.com/makeplane/plane-mcp-server](https://github.com/makeplane/plane-mcp-server) — AI агенты могут взаимодействовать через MCP
- GitHub/GitLab интеграция, линковка commits → issues
- Импорт из Jira, Linear, Asana, ClickUp
- SOC 2, ISO 27001, GDPR
- **Цена**: Free (cloud + self-hosted), Pro $5/user/mo

### Tegon (dev-first)
- Open-source альтернатива Linear
- AI: auto-suggest titles, duplicate detection
- Omni-channel: Slack, Email, Discord, Zendesk → auto-create issues
- Actions framework для автоматизации
- **Цена**: Бесплатно (self-hosted)

### Huly (all-in-one)
- Open-source: issues + docs + chat + calendar
- Заменяет Linear + Notion + Slack
- Self-hosted
- **Цена**: Бесплатно

---

## 8. Port.io — Jira → GitHub Issues → Copilot Pipeline

**Статус**: Production  
**Особенность**: мост между Jira и GitHub

### Как работает
1. AI агент в Port.io генерирует GitHub Issues из Jira tickets с полным контекстом
2. Назначает на GitHub Copilot
3. Copilot создаёт PR
4. PR линкуется обратно к Jira

Работает также с Claude Code, Devin и другими coding agents.

**Источник**: [docs.port.io/guides/all/automatically-resolve-tickets-with-coding-agents](https://docs.port.io/guides/all/automatically-resolve-tickets-with-coding-agents/)

---

## Сравнительная таблица

| Инструмент | Тип | Цена | Auto-PR | Review | Issue→PR | Open Source |
|------------|-----|------|---------|--------|----------|-------------|
| **GitHub Copilot Agent** | Coding agent | $10+/mo | Да | Да | Да | Нет |
| **Kiro (AWS)** | Coding agent | Free tier | Да | Да | Да | Нет |
| **Claude Code Actions** | Review + fix | API costs | Да | Да | Частично | Нет |
| **SWE-Agent** | Research agent | Free + API | Да | Нет | Да | Да |
| **Aider** | Coding tool | Free + API | Да | Нет | Да | Да |
| **CodeRabbit** | Review bot | Free/Pro | Нет | Да | Нет | Нет |
| **Plane** | Tracker + MCP | Free | Нет | Нет | Нет | Да |
| **Tegon** | Tracker + AI | Free | Нет | Нет | Нет | Да |

## Вывод

GitHub Issues — **лучшая бесплатная платформа** для AI-agent-driven workflow в 2026:
- Copilot Coding Agent превращает issues в PR автоматически
- AGENTS.md даёт контекст проекта
- Branch protection обеспечивает safety
- Session logs обеспечивают аудируемость
- Экосистема (SWE-Agent, Aider, Kiro, Claude) богаче чем у Jira
- GitHub Projects даёт Kanban/Sprint бесплатно

Jira нужна только если уже есть корпоративные процессы, которые на ней завязаны.
