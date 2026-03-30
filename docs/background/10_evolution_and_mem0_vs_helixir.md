# Эволюция подхода к контексту + Mem0 vs Helixir: детальное сравнение

## Часть 1: Личная эволюция (нарратив для доклада)

### Этап 1: Утрата контекста
- LLM забывает факты, чат деградирует, нужно создавать новый.
- При создании нового чата — объяснять всё заново.
- Это фундаментальное ограничение transformer architecture — attention mechanism теряет фокус при росте контекста.
- **Пруф**: "The Maximum Effective Context Window" (OAJAIML, Jan 2026) — реальный MECW значительно меньше заявленного ([PDF](https://www.oajaiml.com/uploads/archivepdf/643561268.pdf))

### Этап 2: MD файлы
- Начал хранить контекст в .md файлах.
- При увеличении строк — context window забивается.
- При разделении на много файлов — агент теряется в структуре, пропускает важное.
- **Пруф**: Augment Code (2026) — при 15 rule-файлах "rules not set to always apply were easy for the agent to miss" ([augmentcode.com](https://www.augmentcode.com/tools/best-spec-driven-development-tools))
- **Вывод**: MD хороши для инструкций и policy (20-30 строк). Превратились в .cursor/rules. 
- Коммит в репо: team-level policy (AGENTS.md) = ок. Personal preferences = антипаттерн.

### Этап 3: Тикеты / Issues
- Удобно: скинуть ссылку на тикет, сказать "продолжай".
- Прямое взаимодействие по API → галлюцинации, потеря контекста, дублирование.
- Через MCP tool легче — targeted запросы вместо чтения всего.
- При росте набора тикетов → менеджерить всё разом невозможно, чат деградирует.
- Деление на эпики/стори/подзадачи помогает, но не избавляет от дублирования.
- **Пруф**: "Lost in the Middle" (Liu et al.) — длинный тикет с комментариями = LLM теряет важное в середине
- **Пруф**: GitHub Agentic Workflows (2026): "Start with low-risk outputs… before enabling pull request creation" — агенты без human-in-the-loop дублируют ([github.blog](https://github.blog/ai-and-ml/automate-repository-tasks-with-github-agentic-workflows/))

### Этап 4: Mem0
- Хорошо держит контекст, семантический поиск работает.
- Self-hosted в закрытом контуре дорого: Vector DB + Graph DB (Neo4j) + LLM API = 3 компонента в Docker.
- Обнаруженные ограничения:
  - Нет онтологического графа (подробнее ниже)
  - Все факты на одном уровне восприятия
  - Атомарные факты без каузальных связей
  - Противоречия разрешаются вероятностно (подробнее ниже)

### Этап 5: Helixir
- Нет готового решения на нужном уровне сложности.
- Проблема: не было хранилища, способного связывать вектора и графы → появился HelixDB.
- v0 на Python → накладные расходы на виртуализацию и интерпретатор.
- Переписан на Rust: ~50ms startup, ~15MB RAM, single binary, zero runtime dependencies.
- No-deletion by design: видеть всю цепочку фактов. Минус: заполнение диска.
- Graph depth = 1 (1 соседнее звено): компромисс между глубиной и подробностью.

---

## Часть 2: Mem0 vs Helixir — детальное техническое сравнение

### 2.1 Дедупликация и разрешение конфликтов

#### Mem0: A.U.D.N. цикл (LLM-based)

Mem0 использует LLM как decision engine для каждого нового факта. Цикл называется **A.U.D.N.**:

| Операция | Когда | Что происходит |
|----------|-------|----------------|
| **ADD** | Новый факт, нет похожих в памяти | Добавляется как новая memory |
| **UPDATE** | Новый факт дополняет/обновляет существующий | Существующая memory перезаписывается |
| **DELETE** | Новый факт противоречит существующему | Старая memory **удаляется** |
| **NOOP** | Дубликат или нерелевантно | Ничего не происходит |

**Источник**: VirtusLab (2025): "The A.U.D.N. cycle is a paradigm shift — instead of writing hundreds of lines of code to handle conflicts, developers recast the problem as a tool-selection task for the LLM." ([virtuslab.com](https://virtuslab.com/blog/ai/git-hub-all-stars-2/))

**Источник**: Mem0 Research Paper: "Each new fact is compared to the top s similar entries in the vector database. The LLM then chooses one of four operations." ([mem0.ai/research](https://mem0.ai/research))

**Ключевая проблема**: при DELETE старый факт **удаляется навсегда**. Нет истории противоречия. Нет аудита "что было до того, как LLM решил обновить". При UPDATE — старое значение **перезаписывается**.

**Вероятностность**: решение принимает LLM на основе semantic similarity. Это:
- Не детерминированно (один и тот же факт может быть ADD в одном запуске и UPDATE в другом)
- Зависит от формулировки (синонимы могут не матчиться)
- Может пропустить противоречие если факты сформулированы по-разному

**Источник**: Cortex vs Mem0 (2025): "Mem0 focuses on retrieval accuracy with a static memory store" ([usecortex.ai](https://www.usecortex.ai/blog/cortex-vs-mem0-for-llm-memory-2025-features-pricing))

#### Helixir: Explicit relationship types

| Операция | Когда | Что происходит |
|----------|-------|----------------|
| **ADD** | Новый факт | Создаётся node в графе |
| **UPDATE** | Факт уточняется | Старый node остаётся, создаётся связь UPDATE |
| **SUPERSEDE** | Новый факт заменяет старый | Оба существуют, связаны ребром SUPERSEDE |
| **CONTRADICTS** | Факты противоречат | Оба существуют, связаны ребром CONTRADICTS |
| **NOOP** | Дубликат | Ничего |

**Ключевая разница**: ничего не удаляется. Противоречие — это **явная связь в графе**, а не решение "удалить старое". Агент видит: "Факт A CONTRADICTS Факт B" и может:
- Спросить пользователя "Что актуально?"
- Посмотреть timestamps обоих фактов
- Следовать по цепочке к другим связанным фактам

### 2.2 Граф связей

#### Mem0: Entity-Relationship граф

Mem0g (graph memory) извлекает **entities** и **relationships** из бесед:

1. **Entity Extractor** (LLM-based) идентифицирует: people, places, objects, events
2. **Relations Generator** создаёт labeled edges (triplets): `Alice →[met]→ Bob`, `Alice →[attended]→ GraphConf`
3. Хранится в Neo4j / Memgraph / Neptune / Kuzu

**Что граф хранит** (из документации Mem0):
- "Extract **people, places, and facts**" ([docs.mem0.ai](https://docs.mem0.ai/open-source/features/graph-memory))
- Entity types: Person, Place, Object, Event
- Relationships: generic labeled edges ("works_at", "met", "uses", "lives_in")
- Conflict Detector + Update Resolver для графовых элементов

**Что граф НЕ хранит**:
- Каузальные связи (BECAUSE, IMPLIES)
- Онтологические категории фактов (skill, preference, goal)
- Временные цепочки (SUPERSEDE, CONTRADICTS)
- Reasoning chains

**Ограничения** (подтверждённые):
- Custom entity extraction prompts **не поддерживаются** — hardcoded system prompt. Открытый GitHub issue #3299 (Aug 2025): "The graph search functionality uses a hardcoded system prompt for entity extraction that cannot be customized." ([github.com/mem0ai/mem0/issues/3299](https://github.com/mem0ai/mem0/issues/3299))
- Graph search возвращает `relations` key рядом с vector results, но "graph edges do not reorder those hits automatically" ([docs.mem0.ai](https://docs.mem0.ai/open-source/features/graph-memory))

**Источник**: Mem0 blog (Jan 2026): "Vectors find similar text, but graphs preserve how facts connect across sessions." ([mem0.ai/blog](https://mem0.ai/blog/graph-memory-solutions-ai-agents))

**Источник**: letsdatascience.com: "Mem0 introduced graph memory in January 2026, storing memories as directed labeled graphs where entities are nodes and relationships are edges." ([letsdatascience.com](https://www.letsdatascience.com/blog/ai-agent-memory-architecture))

#### Helixir: Causal + Ontological граф

Helixir граф хранит:
1. **Онтологически типизированные nodes**: 7 типов (skill, preference, goal, fact, opinion, experience, achievement)
2. **Каузальные edges**: IMPLIES, BECAUSE, CONTRADICTS, SUPERSEDE
3. **Vector embeddings** на каждом node (через HelixDB native vector)

**Что граф хранит, чего нет в Mem0**:
- "Тест упал" (fact) BECAUSE "race condition" (fact) IMPLIES "добавить retry" (skill)
- "Используем Selenium" (preference) SUPERSEDE→ "Перешли на Playwright" (preference)
- "Мокируем DB" (opinion) CONTRADICTS "Используем testcontainers" (opinion)

### 2.3 Сводная таблица различий

| Аспект | Mem0 | Helixir |
|--------|------|---------|
| **Дедупликация** | LLM решает (A.U.D.N.) — вероятностно | LLM решает + explicit graph edges |
| **При противоречии** | Старый факт УДАЛЯЕТСЯ | Оба живут, связаны CONTRADICTS |
| **При обновлении** | Старый факт ПЕРЕЗАПИСЫВАЕТСЯ | Оба живут, связаны SUPERSEDE |
| **Аудит истории** | Нет (delete/overwrite) | Полный (append-only graph) |
| **Тип графа** | Entity-Relationship (who/what) | Causal + Ontological (why/how) |
| **Entity types** | Person, Place, Object, Event | skill, preference, goal, fact, opinion, experience, achievement |
| **Edge types** | Generic labeled ("works_at", "met") | Typed causal (IMPLIES, BECAUSE, CONTRADICTS, SUPERSEDE) |
| **Custom extraction** | Нет (hardcoded prompt, issue #3299) | Configurable |
| **Graph DB** | Neo4j / Memgraph (external) | HelixDB (встроенный, graph+vector) |
| **Инфраструктура** | Vector DB + Graph DB + LLM = 3 сервиса | HelixDB + LLM = 2 компонента |
| **Traversal depth** | Configurable (default varies) | Depth=1 (осознанный компромисс) |

### 2.4 Почему это важно для тестирования

**Сценарий: тест падал 3 раза по разным причинам**

**В Mem0:**
```
Memory 1: "Login test failed due to timeout" (stored)
Memory 2: "Login test failed due to race condition" (LLM decides: UPDATE → Memory 1 overwritten)
Memory 3: "Login test failed due to cookie settings" (LLM decides: UPDATE → Memory 2 overwritten)

Результат: в памяти только "cookie settings". 
История потеряна. Агент не знает что были timeout и race condition.
```

**В Helixir:**
```
Fact 1: "Login test failed due to timeout" (fact, t=Jan)
Fact 2: "Login test failed due to race condition" (fact, t=Feb)
  → Fact 2 SUPERSEDE Fact 1
Fact 3: "Login test failed due to cookie settings" (fact, t=Mar)
  → Fact 3 SUPERSEDE Fact 2

Результат: все 3 причины в графе. 
Агент может пройти по цепочке SUPERSEDE и увидеть эволюцию проблемы.
Если тест упадёт в 4-й раз — агент проверит все 3 предыдущих причины.
```

### 2.5 Источники

1. VirtusLab. **GitHub All-Stars #2: Mem0 — Creating memory for stateless AI minds.** 2025. [virtuslab.com](https://virtuslab.com/blog/ai/git-hub-all-stars-2/)
2. **Mem0 Research Paper.** "Extraction and Update phases." [mem0.ai/research](https://mem0.ai/research)
3. VentureBeat. **Mem0's scalable memory promises more reliable AI agents.** 2025. [venturebeat.com](https://venturebeat.com/ai/mem0s-scalable-memory-promises-more-reliable-ai-agents-that-remembers-context-across-lengthy-conversations)
4. Mem0 Docs. **Graph Memory.** "Extract people, places, and facts." [docs.mem0.ai](https://docs.mem0.ai/open-source/features/graph-memory)
5. GitHub Issue #3299. **Allow Custom Prompts for Entity Extraction in Graph Search.** Aug 2025. [github.com/mem0ai/mem0/issues/3299](https://github.com/mem0ai/mem0/issues/3299)
6. Stackademic. **Mem0 Memory Layer — Purpose and Core Functionality.** 2025. [blog.stackademic.com](https://blog.stackademic.com/mem0-memo-ai-memory-layer-purpose-and-core-functionality-375cc5a2bfd0)
7. Mem0 Blog. **Graph Memory for AI Agents.** January 2026. [mem0.ai/blog](https://mem0.ai/blog/graph-memory-solutions-ai-agents)
8. Cortex vs Mem0. 2025. [usecortex.ai](https://www.usecortex.ai/blog/cortex-vs-mem0-for-llm-memory-2025-features-pricing)
9. letsdatascience.com. **AI Agent Memory: Architecture and Implementation.** [letsdatascience.com](https://www.letsdatascience.com/blog/ai-agent-memory-architecture)
10. Oracle Blogs. **Agent Memory: Why Your AI Has Amnesia and How to Fix It.** "Three approaches to contradictory memories." [blogs.oracle.com](https://blogs.oracle.com/developers/agent-memory-why-your-ai-has-amnesia-and-how-to-fix-it)
11. Foster-Fletcher R. **AI Memory Isn't a Feature, It's Infrastructure.** 2025. [fosterfletcher.com](https://fosterfletcher.com/ai-memory-infrastructure/)
