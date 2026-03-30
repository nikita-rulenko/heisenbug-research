# Эксперимент 3: Mem0 Self-Hosted

## TL;DR
Mem0 self-hosted заработал, но потребовал **6 патчей** поверх официального Docker-образа.
Семантический поиск работает. Извлечение фактов из текста через LLM работает частично.
Graph store (Mem0g) не удалось поднять из-за dependency hell с langchain-neo4j.

## Инфраструктура

### Финальный стек
- **Mem0 API Server** — кастомный образ на базе `mem0/mem0-api-server:latest`
- **PostgreSQL 16 + pgvector** — vector store (официальная рекомендация Mem0)
- **Ollama nomic-embed-text** — embeddings (768 dims) через OpenAI-compatible API
- **Cerebras gpt-oss-120b** — LLM для извлечения фактов
- ~~Neo4j~~ — отключён из-за отсутствия langchain-neo4j в образе

### Конфигурация
```
infra/mem0/
├── docker-compose.yml    # Mem0 + PostgreSQL/pgvector
├── Dockerfile            # Патч: psycopg[pool] + main_patched.py
├── main_patched.py       # 4 патча поверх оригинала
├── .env                  # Секреты (Cerebras key, DB passwords)
└── .gitignore            # Защита .env
```

## Хронология проблем и решений

### Проблема 1: Нет места на диске Docker
- **Симптом:** PostgreSQL не может создать WAL-директорию
- **Решение:** `docker system prune -af --volumes` освободил 19 ГБ
- **Вывод:** Docker Desktop на macOS склонен накапливать образы/volumes

### Проблема 2: psycopg_pool отсутствует (баг #3753)
- **Симптом:** `ImportError: Neither 'psycopg' nor 'psycopg2' library is available`
- **Реальная причина:** psycopg 3.2.10 установлен, но `psycopg_pool` — нет
- **Ссылка:** https://github.com/mem0ai/mem0/issues/3753 — известный баг, не исправлен
- **Решение:** Установка `psycopg-pool` + `psycopg-binary` вручную в контейнер
- **Дополнительная сложность:** PyPI был недоступен из Docker (DNS/network issues),
  пришлось скачивать .whl на хосте через `uv` и `curl`, копировать через `docker cp`

### Проблема 3: libpq отсутствует
- **Симптом:** `ImportError: no pq wrapper available` — psycopg не находит libpq
- **Причина:** Образ содержит psycopg (pure Python), но нет ни libpq, ни psycopg-binary
- **Решение:** Установка psycopg-binary (бандлит libpq, 6.7 МБ для linux/aarch64)

### Проблема 4: main.py хардкодит OpenAI
- **Симптом:** LLM и embedder жёстко привязаны к OpenAI API + одному OPENAI_API_KEY
- **Причина:** `main.py` не предусматривает разные провайдеры для LLM и embedder
- **Решение:** Патченый `main_patched.py` с раздельными env vars:
  - `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` — для Cerebras
  - `EMBEDDER_API_KEY`, `EMBEDDER_BASE_URL`, `EMBEDDER_MODEL`, `EMBEDDER_DIMS` — для Ollama

### Проблема 5: Cerebras не принимает параметр `store`
- **Симптом:** `422 body.store: property 'body.store' is unsupported`
- **Причина:** Mem0 OpenAI LLM класс добавляет `store` в запрос — OpenAI-specific параметр
- **Решение:** Monkey-patch `client.chat.completions.create` чтобы убирать `store`

### Проблема 6: pgvector создаёт таблицу с 1536 dimensions
- **Симптом:** `DataException: expected 1536 dimensions, not 768`
- **Причина:** default embedding dims = 1536 (OpenAI), наш nomic-embed-text = 768
- **Решение:** Добавить `embedding_model_dims: 768` в конфиг vector_store + пересоздать таблицы

### Нерешённая проблема: Graph Store (langchain-neo4j)
- **Симптом:** `ImportError: Could not import MemoryGraph for provider 'neo4j': langchain_neo4j is not installed`
- **Причина:** langchain-neo4j тянет за собой: langchain-classic, langchain-core, langgraph,
  neo4j-graphrag, neo4j — массивное дерево зависимостей, ~50+ пакетов
- **Статус:** Отключён через env var `ENABLE_GRAPH_STORE=false`
- **Вывод:** Mem0g (граф-расширение) практически невозможно поднять в offline/restricted сети

## Результаты тестирования

### Добавление памяти (POST /memories)
```json
// Запрос
{"messages": [{"role":"user","content":"В проекте Bean & Brew...62 теста..."}], "user_id": "heisenbug"}

// Ответ — извлечено 3 факта:
{"results": [
  {"memory": "В проекте Bean & Brew...62 теста четырёх уровней: unit (32), integration (13), API (10), usecase (7)", "event": "ADD"},
  {"memory": "Тесты используют in-memory SQLite, table-driven подход с t.Run, хелперы setupTestDB и setupTestServer", "event": "ADD"},
  {"memory": "Архитектура Clean Architecture: entity, usecase, repository, handler", "event": "ADD"}
]}
```
**Latency:** ~2 секунды (Cerebras LLM + Ollama embedding)

### Семантический поиск (POST /search)
```json
// Запрос
{"query": "какие тесты есть в проекте", "user_id": "heisenbug"}

// Ответ — 3 результата с scores:
// 0.33 — "62 теста четырёх уровней" (наиболее релевантный)
// 0.42 — "table-driven подход..."
// 0.51 — "Clean Architecture..." (менее релевантный)
```
**Latency:** ~200 мс (только Ollama embedding + pgvector search)

### Проблема с повторным извлечением
При повторных POST /memories с другим текстом Cerebras (gpt-oss-120b) часто возвращает
пустые результаты — не извлекает новых фактов. Причина: LLM tool call формат Mem0 оптимизирован
под OpenAI gpt-4o и может работать некорректно с другими провайдерами.

## Сравнение с MD-файлами и GitHub Issues

| Критерий | MD-файлы | GitHub Issues | Mem0 |
|----------|----------|---------------|------|
| Setup complexity | Нулевая | Низкая | **Очень высокая** (6 патчей) |
| Семантический поиск | Нет | Нет | **Да** (pgvector) |
| Извлечение фактов | Ручное | Ручное | **Автоматическое** (LLM) |
| Offline | Да | Нет | Частично (embeddings локальны) |
| Dependency hell | Нет | Нет | **Критический** |
| Масштабируемость | Плохая | Средняя | **Хорошая** (pgvector) |
| LLM-агностичность | N/A | N/A | **Плохая** (оптимизирован под OpenAI) |
| Graph relations | Нет | Нет | Теоретически да, на практике нет |

## Оценка по бенчмарку (предварительная)

| Сценарий | Ожидаемая оценка | Комментарий |
|----------|-----------------|-------------|
| S1: Генерация теста | 17/25 | Семантический поиск находит контекст |
| S2: Поиск покрытия | 18/25 | Зависит от качества извлечённых фактов |
| S3: Flaky анализ | 16/25 | Если факты о flaky сохранены |
| S4: Рефакторинг | 15/25 | Нет структурных связей между сущностями |
| S5: E2E тест | 14/25 | Нет паттернов тестирования в памяти |
| S6: Impact analysis | 12/25 | Нет schema↔test связей |
| S7: Обнаружение дублей | 13/25 | Семантика помогает, но нет полного каталога |
| S8: Test plan | 16/25 | Извлечённые факты дают базу |
| S9: Темпоральный контекст | 10/25 | history API есть, но ограничен |
| S10: Оптимизация suite | 14/25 | Частичная картина |
| **Итого (ожидание)** | **~145/250** | **~58%** |

## Ключевые выводы

1. **Self-hosted Mem0 — не "из коробки"**. Официальный Docker-образ нефункционален:
   отсутствуют psycopg_pool, psycopg-binary, langchain-neo4j. Issue #3753 открыт с 2025 года.

2. **Vendor lock-in на OpenAI**. main.py хардкодит provider, model, API key формат.
   Для Cerebras/Ollama потребовались 4 патча в main.py включая monkey-patch.

3. **Семантический поиск — главная ценность**. pgvector + nomic-embed-text дают быстрый
   (~200мс) и качественный поиск по смыслу.

4. **Graph store (Mem0g) нежизнеспособен в self-hosted**. langchain-neo4j тянёт 50+ зависимостей.
   В restricted сети установка невозможна без предварительной подготовки wheels.

5. **Качество извлечения зависит от LLM**. Cerebras gpt-oss-120b работает хуже OpenAI gpt-4o
   для tool call формата Mem0 — многие сообщения не дают новых фактов.

## Ссылки

- Mem0 GitHub: https://github.com/mem0ai/mem0
- Mem0 Research (LOCOMO benchmark): https://mem0.ai/research — 26% uplift vs OpenAI memory
- Issue #3753 (psycopg_pool): https://github.com/mem0ai/mem0/issues/3753
- Issue #3782 (pgvector not working): https://github.com/mem0ai/mem0/issues/3782
- Issue #3950 (psycopg ConnectionPool DNS): https://github.com/mem0ai/mem0/issues/3950
- Mem0 Docker Compose PR #3258: https://github.com/mem0ai/mem0/pull/3258
