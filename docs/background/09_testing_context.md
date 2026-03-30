# Управление контекстом AI-агентов для автотестов

Heisenbug 2026 — конференция о тестировании. Почему тема памяти и контекста здесь критична?

## Проблема: тестовая кодовая база растёт быстрее production-кода

Типичные пропорции: тесты составляют 1-3x от объёма production-кода. Это создаёт уникальные проблемы для AI-агентов.

**Пруфы по соотношению тестов и production-кода:**
- **Miranda et al. (2025)** — анализ 500+ репозиториев: тестовый код и production-код растут синхронно, но "для 100 строк новой бизнес-логики нужно 120-150 строк тестов" ([Test Co-Evolution in Software Projects, Journal of Software: Evolution and Process, 2025](https://bitdive.io/blog/test-to-code-ratio-standards-2026/))
- **Covrig 2 (ICST 2025)** — в зрелых проектах рост TLOC (test lines of code) систематически превышает рост ELOC (executable product code) ([Code, Test, and Coverage Evolution in Mature Software Systems, ICST 2025](https://bitdive.io/blog/test-to-code-ratio-standards-2026/))
- **Стандарт 2026**: healthy project = 50% test code (1:1), mature backend = 50-55% (1:1.2), high-reliability = 65-75% (1:2 – 1:3) ([bitdive.io, 2026](https://bitdive.io/blog/test-to-code-ratio-standards-2026/))

**Пруфы по проблеме context window:**
- **"The Maximum Effective Context Window for Real World Limits of LLMs"** (OAJAIML, January 2026) — исследование показало что реальная эффективная длина контекста значительно меньше заявленной. "Large context windows degrade model performance… agentic systems relying on large context windows will see cascading failures." ([PDF](https://www.oajaiml.com/uploads/archivepdf/643561268.pdf))
- **"Lost in the Middle"** — академическое исследование: производительность LLM падает на 20%+ когда критическая информация находится в середине большого контекста ([hyperdev.matsuoka.com](https://hyperdev.matsuoka.com/p/big-context-isnt-everything-when))
- **Anthropic (2026)** — "Effective Context Engineering for AI Agents": для long-horizon задач нужны специальные техники — compaction, structured note-taking, multi-agent architectures ([anthropic.com/engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents))
- **Stephanie Jarmak (2026)** — "Enterprise codebases are far larger than anything represented in public benchmarks. Linux is 30M LOC, customers have 100B LOC. Context window = 200K max effective (the Hobbit)." ([medium.com](https://medium.com/@steph.jarmak/rethinking-coding-agent-benchmarks-5cde3c696e4a))

Это создаёт 6 конкретных проблем:

1. **Context window exhaustion** — нельзя загрузить все тестовые файлы в контекст. Для проекта с 500 test-файлами это физически невозможно даже с 128K-window. Реальный MECW ещё меньше (OAJAIML, 2026).
2. **Context rot** — когда агент читает 15 тестовых файлов чтобы найти правильный паттерн, он накапливает irrelevant context, качество генерации деградирует. "Context rot hits testing workflows especially hard" ([morphllm.com, 2026](https://morphllm.com/ai-automated-testing)).
3. **Pattern drift** — тестовые конвенции меняются со временем: "раньше мокирование, теперь integration tests с testcontainers".
4. **Knowledge loss** — почему тест написан именно так? Почему выбрали этот подход к фикстурам? Решения теряются между сессиями.
5. **Flaky test debugging** — одни и те же проблемы всплывают повторно: race conditions, порядок выполнения, network timeouts. Агент каждый раз "переоткрывает" проблему.
6. **Test maintenance debt** — UI/API меняется → десятки тестов ломаются. Агент должен знать паттерны исправления, а не разбираться с нуля.

**Пруфы по flaky tests + LLM:**
- **FlakyGuard (Uber, 2025)** — deployed at Uber, автоматически ремонтирует flaky tests через LLM-guided exploration of dynamic call graphs. "Identifies the context problem in LLM-based flaky test repair." ([arxiv.org/html/2511.14002v1](https://arxiv.org/html/2511.14002v1))
- **"On the Flakiness of LLM-Generated Tests"** (arXiv 2601.08998, Jan 2026) — LLM-generated tests сами могут быть flaky если LLM не получает достаточно контекста. Pizzorno & Berger (2025): "GPT-4o generated a flaky test that randomly assigns a value because the valid values were unknown to the model." ([arxiv.org](https://arxiv.org/html/2601.08998v1))
- **"Adaptive Test Healing using LLM/GPT and Reinforcement Learning"** (ICST Companion 2025) — LLM для анализа test logs + RL для self-healing actions. ([manistechmind.com/PDF](https://manistechmind.com/img/icstcomp25aist-id180-p.pdf))
- **Chi et al. (2024)** — "Automated Co-evolution of Production and Test Code Based on Dynamic Validation and LLMs" (REACCEPT, arXiv 2411.11033)

---

## 1. MD файлы — Static Testing Context

### Как это работает для тестов

```markdown
# AGENTS.md

## Testing
- Run tests: `pytest -x --tb=short`
- Test dir: `tests/`
- Fixtures: `tests/conftest.py` (shared), per-module `conftest.py`
- Use factory pattern for test data (factories.py)
- Always test edge cases: empty input, None, boundary values
- For API tests: use `httpx.AsyncClient`, not `requests`
- For DB tests: use `testcontainers` with PostgreSQL
- NEVER mock the database in integration tests
- Flaky tests: check for race conditions in async code first
```

### Реальная практика (2025-2026)
- **AGENTS.md** используется в 60K+ open-source проектах, stewarded by Agentic AI Foundation / Linux Foundation. Поддерживается Cursor, Copilot, Claude Code, Factory, Codex, Jules и другими ([agents.md](https://agents.md/))
- **.cursorrules** с тестовыми стандартами — популярный паттерн в Cursor. Augment Code (2026): "Compliance was strong on focused tasks when rules were tightly scoped with globs." Минус: "rules not set to always apply were easy for the agent to miss" ([augmentcode.com](https://www.augmentcode.com/tools/best-spec-driven-development-tools))
- **Kiro Agent Hooks** — автогенерация тестов при сохранении файла. Scott Logic (2025): Copilot Agent Mode создал "29 test scenarios, 180 individual test steps with 100% pass rate" для TodoMVC по BDD-спецификации ([blog.scottlogic.com](https://blog.scottlogic.com/2025/10/06/delegating-grunt-work.html))
- **Spec-driven testing** — спецификация включает test plan, acceptance criteria, AI генерит тесты по ним. Liu Shangqi / ThoughtWorks (Dec 2025): "Context engineering optimizes agent-LLM interaction" ([thoughtworks.com](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices))
- **Addy Osmani** (2026): "Those who get the most out of coding agents tend to be those with strong testing practices. An agent can 'fly' through a project with a good test suite as safety net. Without tests, the agent might blithely assume everything is fine when in reality it's broken several things." ([addyosmani.com](https://addyosmani.com/blog/ai-coding-workflow/))

### Плюсы для тестирования
- Мгновенный onboarding: новый агент сразу знает `pytest -x`, структуру тестов, конвенции
- Version-controlled: тестовые правила эволюционируют с проектом через Git
- Нулевая стоимость: текстовый файл, нет API-вызовов
- Понятно человеку: можно review-ить и обсуждать

### Минусы для тестирования
- **Статичность**: не учится на ошибках. Если агент 5 раз неправильно создал фикстуру, MD-файл об этом не узнает
- **Нет semantic search**: "как мы тестируем авторизацию?" → нужно знать точный путь к файлу
- **Не масштабируется**: для 500 тестовых файлов нельзя описать все паттерны в одном .md
- **Нет history**: почему тест написан так, а не иначе? MD не хранит reasoning

---

## 2. GitHub Issues MCP — Task-Driven Testing

### Как это работает для тестов

Workflow: Failing test → GitHub Issue → AI Agent reads via MCP → fixes test → PR → comments progress → closes issue.

### Реальная практика (2025-2026)

**GitHub Agentic Workflows** (technical preview, Mar 2026) — Don Syme & Peli de Halleux (GitHub) описывают 6 паттернов автоматизации, из которых 2 напрямую про тесты ([github.blog](https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/)):
1. **Continuous test improvement** — "assess test coverage and add high-value tests"
2. **Continuous quality hygiene** — "proactively investigate CI failures and propose targeted fixes"

**CI Failure Doctor** (GitHub internal, 2026): расследует failures за минуты, создаёт detailed root cause analysis. "60% of investigations lead to fixes within 24-48 hours" ([github.com/gh-aw discussions](https://github.com/github/gh-aw/discussions/15067))

**Mabl MCP Server** — IDE-интеграция для тестов: "Test Creation Agent gives it requirements in plain English, it builds your test suite. MCP Server brings test automation capabilities directly into your IDE" ([testguild.com, 2026](https://testguild.com/7-innovative-ai-test-automation-tools-future-third-wave/); [digitalocean.com](https://www.digitalocean.com/resources/articles/ai-testing-tools))

### Плюсы для тестирования
- **Full audit trail**: каждый сломанный тест = issue с историей расследования
- **Bidirectional**: CI failure → auto-issue → agent reads → fixes → PR → auto-close
- **Collaboration**: QA и AI работают в одном пространстве (comments, labels)
- **Prioritization**: labels (flaky, critical, regression) + assignees
- **Reproducibility**: issue содержит steps to reproduce, logs, screenshots

### Минусы для тестирования
- **Нет semantic memory**: агент не помнит "в прошлый раз этот тест упал из-за race condition"
- **Overhead**: создание issue на каждый failing test может быть noisy
- **Нет test patterns**: issues плоские, нет связей "этот тест ломается каждый раз при обновлении API schema"
- **Нет learning**: агент не учится, каждая issue разбирается с нуля

---

## 3. Mem0 — Persistent Testing Memory

### Как это работает для тестов

Агент пишет/фиксит тесты → Mem0 автоматически извлекает факты из сессии → сохраняет в vector+graph DB → при следующей сессии семантически ищет релевантные memories.

**Пример потока:**

Сессия 1:
```
Developer: "Напиши тест для auth endpoint"
Agent: *пишет тест, использует pytest fixtures*
Mem0.add(): Извлечено: 
  - "Project uses pytest with async fixtures"
  - "Auth tests use httpx.AsyncClient"
  - "Test DB: testcontainers PostgreSQL"
```

Сессия 2 (через неделю):
```
Developer: "Тест регистрации падает"
Mem0.search("auth test failing"): 
  → "Auth tests use httpx.AsyncClient"
  → "Test DB: testcontainers PostgreSQL"
Agent: *уже знает контекст, не спрашивает "какой фреймворк?"*
```

### Плюсы для тестирования
- **Cross-session continuity**: агент помнит паттерны тестирования между сессиями
- **Token savings**: вместо загрузки 500 тестовых файлов — retrieve 5 релевантных фактов. По бенчмарку LOCOMO: 90% сокращение токенов, 26% рост accuracy, 91% снижение latency vs full-context ([mem0.ai/research](https://mem0.ai/research))
- **Auto-extraction**: не нужно вручную обновлять .md файлы — Mem0 сам извлекает "project uses testcontainers"
- **Semantic search**: "как мы тестируем оплату?" найдёт факты даже если слово "оплата" не встречается (через embeddings)
- **Deduplciation**: повторяющиеся факты схлопываются, устаревшие обновляются

### Минусы для тестирования
- **Нет causal understanding**: Mem0 знает "тест упал" и "использовали retry logic", но не связывает "тест упал ПОТОМУ ЧТО race condition ПОЭТОМУ добавили retry"
- **Flat memories**: все факты одного "веса" — нет понимания что "архитектурное решение о тестировании" важнее чем "последний запуск pytest прошёл"
- **LLM cost**: каждый save = LLM-вызов. При активной тестовой сессии (десятки add()) стоимость растёт
- **No working memory**: промежуточные мысли при debugging ("может это race condition? нет, проверил — это timeout") все идут в persistent memory

---

## 4. Helixir — Causal Testing Memory

### Как это может работать для тестов (гипотеза)

**Каузальные цепочки для test debugging:**

```
"Login test fails" 
  --BECAUSE--> "Session cookie not set" 
  --BECAUSE--> "Test server doesn't enable secure cookies in test env"
  --IMPLIES--> "Need TEST_SECURE_COOKIES=false in conftest"
```

Когда login test снова падает через 3 месяца, агент не начинает с нуля — он проходит по каузальной цепочке и сразу проверяет cookie configuration.

**Онтология для тестовых знаний:**

| Тип | Пример для тестирования |
|-----|------------------------|
| **skill** | "Умеет писать pytest async fixtures с testcontainers" |
| **preference** | "Предпочитаем integration tests мокам для DB" |
| **goal** | "Довести coverage до 80% к Q2" |
| **fact** | "CI запускает тесты на Ubuntu 22.04 в Docker" |
| **opinion** | "Мокирование HTTP — зло, лучше wiremock" |
| **experience** | "Flaky тест payment_flow фиксился retry + увеличение timeout до 30s" |
| **achievement** | "Покрыли тестами 100% auth module" |

Агент может запросить: "Все experience связанные с flaky тестами" → получит конкретные кейсы с решениями.

**FastThink для сложного debugging:**

Тест упал. Агент запускает FastThink session:
```
think_start("debug_payment_test")
think_add("Hypothesis 1: race condition in async payment handler")
think_add("Hypothesis 2: test DB не откатил транзакцию")
think_recall("previous payment test failures")  // ← тянет из памяти
think_add("Memory shows: last time it was transaction rollback")
think_conclude("Check transaction isolation in conftest.py")
think_commit()  // ← только conclusion идёт в память
```

Промежуточные гипотезы НЕ загрязняют основную память. Только вывод.

**Temporal filtering для тестов:**

- `recent` (4h): "Что я тестировал в этой сессии?"
- `contextual` (30d): "Какие тесты падали на этом sprint?"
- `deep` (90d): "Как мы исторически тестировали auth?"
- `full`: "Вся история тестовых решений проекта"

**CONTRADICTS для тестовых решений:**

```
"Используем моки для DB в unit тестах"
  --CONTRADICTS--> "Перешли на testcontainers для всех тестов"
```

Агент видит противоречие и задаёт вопрос: "Мы раньше мокировали DB, но потом перешли на testcontainers. Для нового теста — какой подход?"

**SUPERSEDE для эволюции тест-практик:**

```
"Используем Selenium для E2E" --SUPERSEDE--> "Перешли на Playwright"
```

Агент не предложит Selenium-паттерн, потому что знает что он superseded.

### Плюсы для тестирования (гипотетические)
- **Root cause memory**: цепочки причин ускоряют debugging повторяющихся проблем
- **Structured test knowledge**: онтология даёт агенту типизированные факты, а не плоский список
- **Clean debugging**: FastThink изолирует мыслительный процесс от памяти
- **Temporal relevance**: "свежие" паттерны важнее устаревших
- **Evolution tracking**: SUPERSEDE/CONTRADICTS отражают эволюцию тест-практик

### Минусы для тестирования
- **v0.1.1**: нет production case studies в тестировании
- **LLM required**: каждый add_memory = LLM-вызов (как и Mem0)
- **Learning curve**: 7 онтологических типов + каузальные связи — сложнее чем flat memory
- **No ecosystem**: нет интеграций с pytest, Jest, Playwright (пока)

---

## Проблема масштаба: тесты > production code

| Метрика | Типичный проект | Большой проект |
|---------|----------------|----------------|
| Production code | 50K LOC | 500K LOC |
| Test code | 100-200K LOC | 1-2M LOC |
| Test files | 200-500 | 2000-5000 |
| Context needed | ~5-10 файлов на задачу | ~10-30 файлов |
| Context window | 128K tokens | 128K tokens |

**Ключевой инсайт**: context window не растёт пропорционально кодовой базе. Нужны механизмы умного retrieval.

| Подход | Как решает проблему масштаба |
|--------|----------------------------|
| **MD файлы** | Описывает конвенции, но не конкретные файлы. При 2000 тестов — недостаточно |
| **GitHub Issues** | Работает с конкретными failures, но нет обобщения паттернов |
| **Mem0** | Semantic retrieval по вектору — находит релевантные факты из любого объёма. Сжимает контекст на 90% |
| **Helixir** | Semantic + graph traversal + temporal filtering. Может пройти по цепочке "тест → fixture → pattern → convention" |

---

## Сценарии для демо на Heisenbug

### Сценарий 1: "Новый тест для нового endpoint"
- MD: агент знает pytest, fixtures, conventions из AGENTS.md
- GitHub: нет задачи = нет контекста (только если есть issue "add tests for /api/v2/orders")
- Mem0: помнит из прошлых сессий "для API тестов используем httpx, factory_boy для данных"
- Helixir: помнит + знает "API тесты IMPLIES нужны фикстуры auth + test DB"

### Сценарий 2: "Flaky тест падает в CI"
- MD: в AGENTS.md может быть "check for race conditions first"
- GitHub: CI failure → issue → agent reads → investigates → PR
- Mem0: "в прошлый раз login test падал, фиксили увеличением timeout"
- Helixir: "Login test fails BECAUSE session race condition (experienced 3 times). Fix: add retry + increase timeout"

### Сценарий 3: "Рефакторинг — 50 тестов сломались"
- MD: конвенции не помогут — нужно знать конкретные паттерны
- GitHub: 50 issues? Слишком noisy. Один meta-issue? Нет деталей
- Mem0: "помню паттерн: при рефакторинге auth менять все test_auth_* fixtures в conftest"
- Helixir: "auth refactoring IMPLIES update conftest.py fixtures. Previous experience: 30 тестов починены заменой AuthFactory"

### Сценарий 4: "Эволюция тест-стратегии"
- MD: обновляется вручную, может отставать от реальности
- GitHub: нет механизма трекинга эволюции (только если есть ADR-issues)
- Mem0: помнит текущие практики, но не связывает "было → стало"
- Helixir: "Selenium SUPERSEDE→ Playwright. Mock DB SUPERSEDE→ Testcontainers" — явная эволюция

---

## Источники и ссылки

### Соотношение тестов и production-кода
1. Miranda C., Avelino G., Santos Neto P. **Test Co-Evolution in Software Projects: A Large-Scale Empirical Study.** Journal of Software: Evolution and Process, 2025.
2. **Covrig 2 (ICST 2025).** Code, Test, and Coverage Evolution in Mature Software Systems. International Conference on Software Testing, Verification and Validation, 2025.
3. Chi J. et al. **Automated Co-evolution of Production and Test Code Based on Dynamic Validation and LLMs (REACCEPT).** arXiv 2411.11033, 2024.
4. [Test to Code Ratio: Why 50%+ Test Code is the New Standard in 2026](https://bitdive.io/blog/test-to-code-ratio-standards-2026/) — bitdive.io, 2026.

### Context window и его ограничения
5. **The Maximum Effective Context Window for Real World Limits of LLMs.** OAJAIML, January 2026. [PDF](https://www.oajaiml.com/uploads/archivepdf/643561268.pdf)
6. **"Lost in the Middle: How Language Models Use Long Contexts."** Liu et al., 2023. (referenced in [hyperdev.matsuoka.com](https://hyperdev.matsuoka.com/p/big-context-isnt-everything-when))
7. **Effective Context Engineering for AI Agents.** Anthropic, 2026. [anthropic.com/engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
8. Jarmak S. **Rethinking Coding Agent Benchmarks.** Medium, 2026. [medium.com](https://medium.com/@steph.jarmak/rethinking-coding-agent-benchmarks-5cde3c696e4a)
9. [Context rot hits testing workflows — AI Automated Testing](https://morphllm.com/ai-automated-testing) — morphllm.com, 2026.

### Flaky tests + LLM
10. **FlakyGuard: Automatically Fixing Flaky Tests at Industry Scale.** Uber, 2025. [arxiv.org/html/2511.14002v1](https://arxiv.org/html/2511.14002v1)
11. **On the Flakiness of LLM-Generated Tests for Industrial and Open-Source Systems.** arXiv 2601.08998, January 2026. [arxiv.org](https://arxiv.org/html/2601.08998v1)
12. **Adaptive Test Healing using LLM/GPT and Reinforcement Learning.** ICST Companion 2025. [PDF](https://manistechmind.com/img/icstcomp25aist-id180-p.pdf)
13. **Using Large Language Models for Predicting Flaky Test Fix Categories.** arXiv 2307.00012v4. [arxiv.org](https://arxiv.org/html/2307.00012v4)
14. **Automating Detection and Root-Cause Analysis of Flaky Tests.** arXiv 2603.09029v1, March 2026. [arxiv.org](https://arxiv.org/html/2603.09029v1)

### MD файлы и Spec-Driven Development
15. [AGENTS.md](https://agents.md/) — open standard, Agentic AI Foundation / Linux Foundation. Used in 60K+ projects.
16. Liu Shangqi. **Spec-driven development: Unpacking one of 2025's key new practices.** ThoughtWorks, Dec 2025. [thoughtworks.com](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)
17. Addy Osmani. **My LLM coding workflow going into 2026.** [addyosmani.com](https://addyosmani.com/blog/ai-coding-workflow/)
18. [6 Best Spec-Driven Development Tools for AI Coding in 2026](https://www.augmentcode.com/tools/best-spec-driven-development-tools) — Augment Code.
19. Scott Logic. **Delegating the Grunt Work: AI Agents for UI Test Automation.** October 2025. [blog.scottlogic.com](https://blog.scottlogic.com/2025/10/06/delegating-grunt-work.html)

### GitHub Agentic Workflows и AI-тестирование
20. Don Syme & Peli de Halleux. **Automate repository tasks with GitHub Agentic Workflows.** GitHub Blog, 2026. [github.blog](https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/)
21. **Agent Performance Report** — GitHub Agentic Workflows. [github.com/gh-aw discussions](https://github.com/github/gh-aw/discussions/15067)
22. [12 AI Test Automation Tools QA Teams Actually Use in 2026](https://testguild.com/7-innovative-ai-test-automation-tools-future-third-wave/) — TestGuild.
23. [13 AI Testing Tools to Streamline Your QA Process in 2026](https://www.digitalocean.com/resources/articles/ai-testing-tools) — DigitalOcean.

### Mem0 и AI-память
24. **Mem0: Memory Layer for AI Applications.** LOCOMO benchmark results: 26% accuracy↑, 91% latency↓, 90% tokens↓. [mem0.ai/research](https://mem0.ai/research)
25. [AI Memory Layer Guide](https://mem0.ai/blog/ai-memory-layer-guide) — Mem0, December 2025.
26. [Graph Memory for AI Agents](https://mem0.ai/blog/graph-memory-solutions-ai-agents) — Mem0, January 2026.

### Общие обзоры AI в тестировании
27. **LLMs in Test Automation: The Complete Guide for 2026.** [folio3.ai](https://www.folio3.ai/blog/llms-in-test-automation-guide/)
28. **LLMs in Software Testing 2026.** [accelq.com](https://www.accelq.com/blog/llm-in-software-testing/)
29. **State of Testing Report 2025.** PractiTest. [PDF](https://www.practitest.com/assets/pdf/stot-2025.pdf)
30. **AI Copilot Code Quality: 2025 Data.** GitClear, 211M lines analyzed. [gitclear.com](https://www.gitclear.com/ai_assistant_code_quality_2025_research)
31. **A Review of Large Language Models for Automated Test Generation.** MDPI AI, 2025. [mdpi.com](https://www.mdpi.com/2504-4990/7/3/97)
32. John Vester. **Effectively Managing AI Agents for Testing.** DEV Community, 2026. [dev.to](https://dev.to/johnjvester/effectively-managing-ai-agents-for-testing-iie)
