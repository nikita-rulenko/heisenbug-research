# Финальная таблица для демо — 5 подходов

## 1. MD файлы (AGENTS.md / .cursorrules / spec.md)

**Что это**: Статичные Markdown-файлы в репозитории, которые AI-агент читает при старте сессии.  
**Зрелость**: Стандарт де-факто (2025-2026).

## 2. GitHub Copilot Coding Agent (выбран для демо)

**Что это**: Автономный coding-агент от GitHub. Человек создаёт issue, assignит на `@copilot`, агент подхватывает задачу, создаёт ветку, пишет код, открывает PR, ведёт трек через session logs и реагирует на комментарии в PR.

**Почему выбран**:
- Самый зрелый и узнаваемый инструмент в категории (15M+ разработчиков)
- **Free tier**: 50 premium requests/month + 2000 code completions — достаточно для демо
- Pro: $10/mo, 300 premium requests — дёшево для любой команды
- Лучший UX: assign issue → 👀 emoji → draft PR → session logs → PR comments
- Поддерживает MCP серверы, видит изображения в issues
- Соблюдает branch protection, требует approve перед CI/CD
- AGENTS.md определяет контекст проекта

**Как работает**:
1. Создаёшь GitHub Issue с описанием задачи
2. Assignишь на `@copilot` (через UI или CLI: `gh agent-task create "..."`)
3. Агент ставит 👀, загружает VM, клонирует репо, анализирует код через RAG
4. Создаёт ветку `copilot/...`, пишет код, коммитит
5. Открывает draft PR с описанием, обновляет по мере работы
6. Session logs показывают reasoning и шаги агента
7. Человек оставляет комментарии в PR → агент реагирует

**Ограничения Free tier**:
- 50 premium requests/month (каждая сессия агента = 1 premium request)
- Нет доступа к новейшим моделям (только Claude 3.5 Sonnet и GPT-4.1)
- Response times варьируются в peak hours

**Альтернативы (рассмотрены, но не выбраны)**:
| Альтернатива | Почему не подходит |
|-------------|-------------------|
| Kiro (AWS) | Free tier есть, но менее зрелый, performance issues |
| SWE-Agent | Open source, но one-shot fixer, не трекает работу в comments |
| Open SWE | **DEPRECATED** (LangChain объявил deprecation) |
| Aider | Git-native, но нет нативного issue→PR workflow |

## 3. Mem0 Framework

**Что это**: Production-ready memory layer для AI-агентов. Гибридная архитектура (vector + graph).

### Platform (Cloud) vs Open Source (Self-hosted)

| Аспект | Platform (Cloud) | Open Source (Self-hosted) |
|--------|-----------------|--------------------------|
| **Время до первой memory** | 5 минут | 15-30 минут → часы |
| **Инфраструктура** | Managed (Mem0 servers) | Своя (VM + Vector DB + Graph DB) |
| **Цена** | Free: 10K memories / Starter: $19/mo / Pro: $249/mo | Бесплатно + инфраструктура |
| **Vector DB** | Managed (оптимизирован) | 24+ вариантов (Qdrant, Chroma, Pinecone, Milvus...) |
| **LLM** | Managed (оптимизирован) | 16+ вариантов (OpenAI, Anthropic, Ollama, Together...) |
| **Graph Memory** | Managed | Self-configured |
| **Custom categories** | Да | Ограничено |
| **Webhooks** | Да | Нет |
| **Memory export** | Да | Нет |
| **Memory filters v2** | Да | Через metadata |
| **Auto-scaling** | Да | Manual |
| **High availability** | Built-in | DIY |
| **Compliance** | SOC 2, GDPR included | Своя ответственность |
| **Data residency** | US (расширяемо) | Любая юрисдикция |
| **Multimodal** | Да | Да |
| **SDK** | Python, JavaScript | Python, JavaScript |
| **Setup API key** | 1 env variable | Конфигурация LLM + embedder + vector DB |

### Рекомендация
- **Для демо и быстрого старта** → Platform (Free: 10K memories)
- **Для production с data sovereignty** → Open Source
- **Для enterprise** → Platform Pro/Enterprise ($249+/mo, SOC 2, GDPR)

### Ключевые интеграции
- **Нативно**: CrewAI, Flowise, Langflow
- **SDK**: LangChain, LlamaIndex, Vercel AI SDK
- **AWS Agent SDK** — эксклюзивный memory provider
- **MCP Server**: Mem0 MCP для Cursor / Claude Desktop

## 4. HelixDB

**Что это**: Open-source graph-vector database на Rust. Единая БД для семантического поиска + графовых запросов.

### Adoption

| Компания/Организация | Статус | Источник |
|---------------------|--------|---------|
| **UnitedHealthcare** | Разработчики используют | helix-db.com (listed on site) |
| **Y Combinator** | X25 batch, backed | ycombinator.com/companies/helixdb |
| **Nvidia** | Investor/backer | helix-db.com |
| **Vercel** | Investor/backer | helix-db.com |
| YC X25 startups | Early adopters | YC batch |

**Revenue**: ~$550K с командой из 5 человек (2025, по данным GetLatka).

### Важный контекст
HelixDB — молодой проект (2025). Adoption ограничен стартапами и YC-экосистемой. Enterprise-клиенты пока не публичны. UnitedHealthcare — единственная крупная компания, упомянутая на сайте (уровень использования неизвестен — может быть один разработчик в personal project).

## 5. Helixir

**Что это**: Онтологический каузальный memory framework на HelixDB. Единственный фреймворк, который строит цепочки причин (IMPLIES, BECAUSE, CONTRADICTS).

### Позиционирование
> Mem0, Zep, Letta — все они решают проблему "агент забывает между сессиями". Helixir решает другую проблему: "агент помнит факты, но не понимает причинно-следственные связи".

### Архитектурное сходство с Mem0
Как и Mem0, Helixir **обязательно использует LLM** в pipeline:
- `add_memory` → LLM Atomic Fact Extraction → Smart Deduplication (ADD/UPDATE/SUPERSEDE/NOOP) → Embedding → HelixDB
- `HELIX_LLM_API_KEY` и `HELIX_EMBEDDING_API_KEY` — **required** env variables
- Рекомендуемый стек: Cerebras (~3000 tok/s, free tier) + OpenRouter (embeddings)
- Полностью локальный вариант: Ollama (llama3:8b + nomic-embed-text)

### Уникальные features, которых нет ни у кого
1. **Каузальные цепочки**: IMPLIES / BECAUSE / CONTRADICTS
2. **FastThink**: изолированный scratchpad для рассуждений (не загрязняет основную память)
3. **Онтология**: 7 типов фактов (skill, preference, goal, fact, opinion, experience, achievement)
4. **Cognitive Protocol**: автоматические триггеры recall/save
5. **Temporal filtering**: 4 режима (4h / 30d / 90d / all)
6. **Timeout recovery**: незавершённые рассуждения сохраняются с маркером [INCOMPLETE]

### Честная позиция
- v0.1.1, 74 stars, 1 maintainer
- LLM обязателен (как и у Mem0) — это не zero-cost решение
- Нет production case studies
- Нет бенчмарков на стандартных тестах
- Это research-level проект, не enterprise solution
