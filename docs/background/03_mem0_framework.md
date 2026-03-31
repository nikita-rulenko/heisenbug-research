# Mem0 — AI Memory Framework

**Ссылки:**
- GitHub: https://github.com/mem0ai/mem0
- Документация: https://docs.mem0.ai/
- Сайт: https://mem0.ai/
- Research (LoCoMo benchmark): https://mem0.ai/research
- PyPI: https://pypi.org/project/mem0ai/
- pgvector: https://github.com/pgvector/pgvector
- MCP-server mem0: https://github.com/mem0ai/mem0-mcp

## Обзор

**Mem0** — инфраструктурная платформа памяти для AI-агентов. Позиционируется как "default memory layer for AI". Основана Taranjeet Singh (ex-Paytm, Khatabook) и Deshraj Yadav (ex-Tesla).

- **GitHub Stars**: 47.8K+ (крупнейший в категории)
- **Downloads**: 14M+
- **API calls**: 35M (Q1 2025) → 186M (Q3 2025) — рост 5x
- **Финансирование**: $24M Series A
  - Lead: Basis Set Ventures
  - Ранее: Seed от Kindred Ventures
  - Участники: Peak XV Partners, GitHub Fund, Y Combinator
  - Стратегические: CEO Datadog, Supabase, PostHog, ex-GitHub, Weights & Biases, Scott Belsky, Dharmesh Shah
- **Источник**: [prnewswire.com, Oct 2025](https://www.prnewswire.com/news-releases/mem0-raises-24m-series-a-to-build-memory-layer-for-ai-agents-302597157.html)

## Архитектура

### Гибридная система памяти
- **Vector store** — семантический поиск через embeddings
- **Graph database** — граф знаний для relationship mapping
- **Dual pipeline**: extraction → deduplication → storage → retrieval

### Варианты
- **Mem0** (standard) — vector-based, ~7K токенов на разговор
- **Mem0ᴳ** (graph variant) — graph + vector, ~14K токенов, лучше temporal и relational queries

### Развёртывание
- **Managed SaaS** (mem0.ai) — нулевое управление инфраструктурой
- **Self-hosted** — полный контроль и data sovereignty
- **MCP Server** — интеграция с Cursor, Claude Desktop

## Кто использует

| Категория | Примеры |
|-----------|---------|
| Frameworks | CrewAI, Flowise, Langflow (нативная интеграция) |
| Cloud | **AWS Agent SDK** — эксклюзивный memory provider |
| Enterprise | Thousands of Fortune 500 companies (по данным Mem0) |
| SDK | LangChain, LlamaIndex, Vercel AI SDK |

## Бенчмарки (LOCOMO benchmark)

| Метрика | Mem0 | OpenAI Memory | LangMem | MemGPT/Letta |
|---------|------|---------------|---------|--------------|
| J-score (overall) | Лучший | Средний | Слабый | Средний |
| Latency (p95) | 1.44s | 0.89s | 59.82s | — |
| Tokens/conversation | ~7K | — | — | — |
| Multi-hop reasoning | Лучший | Слабый | Средний | Средний |
| Temporal queries (Mem0ᴳ) | J: 58.13 | — | — | — |

> Key milestone: Mem0 achieving **87%+ accuracy** on long-term memory tasks while remaining self-hostable.
> — "2025 AI Infrastructure Year in Review"

## Плюсы

1. **Production-ready** — самый зрелый продукт в категории
2. **Простая интеграция** — 3 строки кода для подключения
3. **Framework-agnostic** — работает с любым LLM
4. **Гибридная архитектура** — vector + graph
5. **Масштабируемость** — sub-second retrieval при масштабе
6. **Экосистема** — крупнейшее сообщество (47.8K stars)
7. **AWS backing** — эксклюзивный provider для Agent SDK
8. **Managed SaaS** — нулевой ops overhead
9. **Auto memory extraction** — LLM автоматически извлекает факты
10. **Compression engine** — реально снижает token costs

## Минусы

1. **Disputed benchmarks** — конкуренты оспаривают метрики
2. **Integration issues** — GitHub issues с LangChain/LangGraph/Memgraph
3. **SaaS-first** — self-hosting кажется вторичным приоритетом
4. **Vendor lock-in** при использовании managed-версии
5. **Compliance obligations** — GDPR, HIPAA, SOC 2 при хранении user data
6. **Нет настоящего reasoning** — запоминает факты, но не строит причинно-следственные цепочки
7. **Token overhead** — graph variant удваивает стоимость (~14K vs ~7K)
8. **Нет FastThink** — нет изолированного scratchpad для reasoning
9. **Нет онтологической типизации** — факты без категоризации (skill/goal/preference)
10. **Closed-source core** (managed version)

## Сравнение с конкурентами

| Фича | Mem0 | Zep | Letta | LangMem | Cognee |
|------|------|-----|-------|---------|--------|
| Graph Memory | Yes | Yes | Limited | Limited | Yes |
| Managed Service | Yes | Yes | Yes | No | No |
| Framework-Agnostic | Yes | Yes | Yes | No (LangChain) | Yes |
| Sub-Second Retrieval | Yes | Conditional | No | No | No |
| Auto Extraction | Yes | Yes | Yes | No | No |
| Stars | 47.8K | 4.1K | 21.2K | 1.3K | — |
| Pricing | Free + $19-249/mo | Free + $25+/mo | Free + $20-200/mo | Free (OSS) | Free (OSS) |
