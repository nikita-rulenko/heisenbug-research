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
**Latency:** p50=101мс, p95=213мс (только Ollama embedding + pgvector search)

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

## Результаты бенчмарка

### Benchmark v2 — Part A (12 сценариев, шкала 1-4, отдельный evaluator)

> **Generator**: gpt-oss-120b | **Evaluator**: zai-glm-4.7 (GLM 4.7 MoE 358B/32B active)
> **Тесты**: 175 функций (241 с подтестами) | **Контекст**: 21 эпизод, ~20K chars
> **3 прогона**, медианы по сценариям

**Median: 125/192 (65.1%) — 1-е место** | Mean: 121.33 ± 10.97 | Range: 109–130

| Сценарий | Median | Runs | Комментарий |
|----------|--------|------|-------------|
| S1: Генерация теста | 0/16 | [0, 14, 0] | Та же проблема, что у MD — стохастичность генерации |
| S2: Покрытие endpoint | 11/16 | [11, 8, 11] | На уровне MD и GH Issues |
| S3: Flaky анализ | 12/16 | [7, 13, 12] | Семантический поиск находит факты о flaky |
| S4: Рефакторинг | **13/16** | [13, 14, 9] | **Лучший результат** — семантика помогает связать сущности |
| S5: E2E тест | 10/16 | [16, 10, 5] | Высокая дисперсия — нестабильный retrieval паттернов |
| S6: Impact analysis | 11/16 | [16, 8, 11] | Средне, но высокий потолок (16 в run 1) |
| S7: Обнаружение дублей | 4/16 | [4, 4, 5] | Ceiling effect как у всех |
| S8: Test plan | **15/16** | [15, 15, 14] | **Лучший среди всех подходов** |
| S9: Темпоральный | 4/16 | [5, 4, 4] | Не лучше MD — в v2 нет temporal advantage |
| S10: Оптимизация | 14/16 | [14, 14, 12] | Стабильно высокий |
| S11: Coverage matrix | **13/16** | [10, 13, 13] | **Лучший** — семантика группирует тесты |
| S12: Dependencies | 13/16 | [14, 13, 13] | Стабильно хорошо |

**Ключевое наблюдение v2:** Mem0 лидирует благодаря S4 (рефакторинг, 13 vs 7-9) и S11 (coverage
matrix, 13 vs 8-11). Семантический поиск даёт преимущество на задачах со сложным retrieval —
там, где нужно собрать информацию из разных частей контекста. При этом S8 (test plan) тоже лучший
(15 vs 12-13), что подтверждает: извлечённые факты хорошо ложатся на задачи планирования.

---

### Benchmark v1 — Part A (10 сценариев, шкала 0-5, self-evaluation)

**Part A: 138/250 (55.2%)**

| Сценарий | Оценка | Комментарий |
|----------|--------|-------------|
| S1: Генерация теста | 20/25 | Семантический поиск находит контекст |
| S2: Поиск покрытия | 8/25 | Неполное извлечение фактов |
| S3: Flaky анализ | 25/25 | Факты о flaky сохранены и найдены |
| S4: Рефакторинг | 0/25 | Нет структурных связей между сущностями |
| S5: E2E тест | 10/25 | Нет паттернов тестирования в памяти |
| S6: Impact analysis | 11/25 | Нет schema↔test связей |
| S7: Обнаружение дублей | 1/25 | Семантика недостаточна без полного каталога |
| S8: Test plan | 20/25 | Извлечённые факты дают базу |
| S9: Темпоральный контекст | 18/25 | Единственный подход с хорошим результатом на S9 |
| S10: Оптимизация suite | 25/25 | Семантический поиск нашёл релевантный контекст |

**Part B: 88/125 (70.4%)** | **Part C: 123/125 (98.4%)** | **Итого: 349/500 (69.8%)**

## Ключевые выводы

1. **Self-hosted Mem0 — не "из коробки"**. Официальный Docker-образ нефункционален:
   отсутствуют psycopg_pool, psycopg-binary, langchain-neo4j. Issue #3753 открыт с 2025 года.

2. **Vendor lock-in на OpenAI**. main.py хардкодит provider, model, API key формат.
   Для Cerebras/Ollama потребовались 4 патча в main.py включая monkey-patch.

3. **Семантический поиск — главная ценность**. pgvector + nomic-embed-text дают быстрый
   (p50=101мс) и качественный поиск по смыслу.

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
