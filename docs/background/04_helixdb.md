# HelixDB — Graph-Vector Database

## Обзор

**HelixDB** — open-source граф-векторная база данных, написанная на Rust. Объединяет graph и vector типы данных в единой системе для RAG и AI-приложений.

- **Основатели**: George Curtis, Xavier Cochran
- **Основана**: 2025, San Francisco
- **Y Combinator**: X25 batch
- **Бэкеры**: Y Combinator, Nvidia, Vercel
- **HN Launch**: 237 points, 112 comments
- **Источники**:
  - [helix-db.com](https://www.helix-db.com/)
  - [YC page](https://www.ycombinator.com/companies/helixdb)
  - [HN discussion](https://news.ycombinator.com/item?id=43975423)
  - [GitHub](https://github.com/helixdb)

## Архитектура

### Ядро
- **Язык**: Rust — memory safety, zero GC, высокая производительность
- **Модель данных**: property graph с векторами как first-class типы
- **Query language**: HelixQL — type-safe, компилируется в Rust код
  - Синтаксис: Rust-like с влиянием Gremlin, Cypher, SQL
  - Функциональные traversals
  - Schema-based, type-checked up front

### Компиляция запросов
Уникальная особенность: запросы **транспилируются в Rust** и встраиваются прямо в сервер как native endpoints. Нет runtime компиляции запросов → минимальная латентность.

### Версии
- **Helix Lite** — локальный, для прототипирования и low-latency
- **Helix Enterprise** — distributed, high-availability, SOC II compliance

## Бенчмарки

| Сравнение | Результат |
|-----------|---------|
| vs Pinecone/Qdrant (vectors) | На уровне (on par) |
| vs Neo4j (graph) | **2-3 порядка быстрее** |

## Кто использует

| Компания | Статус |
|----------|--------|
| **UnitedHealthcare** | Разработчики используют (указано на сайте) |
| Y Combinator startups | X25 batch участники |

> HelixDB пока молодой проект — adoption ограничен, но backing от YC/Nvidia/Vercel создаёт сильный сигнал.

## Ключевые use cases

1. **RAG** — hybrid similarity + relationship queries
2. **Codebase indexing** — vectorized snippets + AST graph
3. **AI agent memory** — knowledge graphs с семантическим поиском
4. **Recommendation engines** — user preferences + item relationships
5. **Knowledge management** — structured + unstructured data

## Плюсы

1. **Unified graph + vector** — нет необходимости в двух БД
2. **Написан на Rust** — memory safety, экстремальная производительность
3. **Compiled queries** — HelixQL → Rust → native endpoints
4. **Type-safe** — ошибки ловятся на этапе компиляции
5. **Open source** — бесплатный Helix Lite
6. **Pipelined traversals** — параллельные графовые обходы
7. **Strong backing** — YC, Nvidia, Vercel
8. **Растущее сообщество** — HN reception очень позитивный

## Минусы

1. **Молодой проект** (2025) — ограниченный production track record
2. **Новый query language** (HelixQL) — кривая обучения
3. **Маленькая экосистема** — мало SDK, клиентов, интеграций
4. **Нет proven scale** — enterprise tier ещё не battle-tested
5. **Ограниченная документация** по сравнению с Neo4j/Pinecone
6. **Нет встроенных embeddings** — нужен внешний embedding provider
7. **Зависимость от двух основателей** — bus factor
8. **Критика "yet another query language"** от HN community
9. **Multi-paradigm risk** — SurrealDB, Gel, Helix — подобные проекты часто не доживают до зрелости
