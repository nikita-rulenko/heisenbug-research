# Сравнительная таблица подходов к управлению контекстом AI-агентов

## Таксономия подходов

| # | Подход | Тип | Персистентность | Семантика | Каузальность |
|---|--------|-----|-----------------|-----------|--------------|
| 1 | Spec-Driven (AGENTS.md) | Статичный файл | Файловая система | Нет | Нет |
| 2 | Jira/Тикеты | Структурированный трекер | БД трекера | Нет | Нет |
| 3 | Mem0 | Memory framework | Vector + Graph DB | Да (embeddings) | Нет |
| 4 | HelixDB + custom | Graph-vector DB | Native graph+vector | Да | Возможна |
| 5 | Helixir (HelixDB) | Ontological memory | HelixDB | Да | Да (native) |

## Детальное сравнение

| Критерий | AGENTS.md / SDD | Jira/Tickets | Mem0 | HelixDB (raw) | Helixir |
|----------|-----------------|--------------|------|---------------|---------|
| **Хранение** | .md файлы в repo | Jira/Linear DB | Vector + Graph DB | Graph-Vector DB | HelixDB |
| **Поиск** | Полнотекстовый | Текстовый + фильтры | Semantic (vector) | Semantic + Graph | Semantic + Graph + Ontology |
| **Автоматическое сохранение** | Нет (ручное) | Частичное | Да (LLM extraction) | Нет (API) | Да (LLM extraction) |
| **Забывание** | Нет | Нет | Да (auto-forget) | Нет (manual) | Да (SUPERSEDE/NOOP) |
| **Каузальные связи** | Нет | Нет (только comments) | Нет | Возможно (graph) | Да (IMPLIES/BECAUSE/CONTRADICTS) |
| **Working memory** | Нет | Нет | Нет | Нет | Да (FastThink) |
| **Типизация фактов** | Нет | Тип тикета | Нет | Schema-based | Онтология (7 типов) |
| **Temporal filtering** | Нет | По дате | Нет (all-or-nothing) | Нет | 4 режима (4h/30d/90d/all) |
| **MCP интеграция** | Нативная (файлы) | API/webhooks | Да (Mem0 MCP) | Нет нативного MCP | Да (native MCP) |
| **Аудируемость** | Git history | Полная (трекер) | Ограничена | API logs | Ограничена |
| **Масштабируемость** | Ограничена (context window) | Хорошая (DB) | Отличная (SaaS) | Отличная (Rust) | Хорошая (Rust, self-hosted) |
| **Production-readiness** | Высокая | Высокая | Высокая | Средняя | Низкая (early) |
| **Порог входа** | Минимальный | Низкий | Средний (3 строки кода) | Высокий (HelixQL) | Средний (MCP tools) |
| **Стоимость** | Бесплатно | $0-49/agent/mo | Free-$499/mo | Free (OSS) | Free (OSS) |
| **Community size** | Огромная | Огромная | 47.8K stars | ~1K stars | 74 stars |
| **Enterprise support** | Cursor Pro ($20/mo) | Atlassian Enterprise | AWS Agent SDK | Helix Enterprise | Нет |

## Матрица принятия решений

### Когда выбирать каждый подход:

| Подход | Лучше всего для | Не подходит для |
|--------|----------------|-----------------|
| **AGENTS.md** | Быстрый старт, малые проекты, одиночная разработка | Долгосрочная память, мультиагентные системы |
| **Jira/Tickets** | Команды с существующими процессами, аудит, compliance | Real-time AI memory, semantic search |
| **Mem0** | Production AI agents, customer support, SaaS | Каузальное reasoning, бюджетные проекты |
| **HelixDB** | Custom AI infrastructure, RAG, knowledge graphs | Quick MVP, нет Rust-экспертизы |
| **Helixir** | Research, causal reasoning, ontological memory | Production enterprise, нужна поддержка |

## Эволюционный путь

```
AGENTS.md (день 1)
    ↓ масштаб растёт
Jira/Tickets (структурированный трекинг)
    ↓ нужна семантика
Mem0 (production memory layer)
    ↓ нужна каузальность и reasoning
Helixir/HelixDB (ontological + causal memory)
```

## Прогнозы индустрии (2026)

1. **Memory consolidation** — из 6+ frameworks останется 2-3 победителя (источник: "2025 AI Infrastructure Year in Review")
2. **Durability becomes table stakes** — каждый серьёзный фреймворк обеспечит durable execution к концу 2026
3. **Memory market** — $6.27B (2025) → $28.45B (2030)
4. **78% организаций** уже используют AI в production, 85% развернули агентов минимум в одном workflow
