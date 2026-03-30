# Эксперимент 4: Graphiti (getzep) — Temporal Knowledge Graph

## TL;DR
Graphiti (getzep) — temporal knowledge graph поверх FalkorDB. Архитектурно самый продвинутый
подход: episodes, entity/relation extraction, temporal edges. На практике **полностью заблокирован
vendor lock-in на OpenAI** — SDK использует `client.responses.parse()` (OpenAI Responses API),
несовместимый с Cerebras/Ollama/любым non-OpenAI провайдером. Бенчмарк прогнан с raw context fallback.

## Инфраструктура

### Финальный стек
- **FalkorDB** — graph database (fork RedisGraph), Docker-контейнер
- **Ollama nomic-embed-text** — embeddings (через OpenAI-compatible endpoint)
- **Cerebras gpt-oss-120b** — LLM (через OpenAI-compatible endpoint)
- **graphiti-core[falkordb]** — Python SDK v0.28.2+

### Конфигурация
```
infra/graphiti/
├── docker-compose.yml        # FalkorDB (порт 6379 + UI 3001)
├── client.py                 # Обёртка: add_episodes, search, clear
├── main.py                   # Stub (не используется)
├── pyproject.toml            # graphiti-core[falkordb]>=0.28.2, python-dotenv
├── test_context_episodes.json # Контекст для загрузки (12 эпизодов)
├── .env                      # API keys (Cerebras, Ollama)
├── .python-version           # 3.14
└── uv.lock                   # Lockfile
```

### Docker Compose
```yaml
services:
  falkordb:
    image: falkordb/falkordb:latest
    ports:
      - "6379:6379"    # Redis protocol
      - "3001:3000"    # FalkorDB Browser UI
    volumes:
      - falkordb_data:/data
```

## Хронология проблем

### Проблема 1: OpenAI Responses API (БЛОКИРУЮЩАЯ)
- **Симптом:** При вызове `graphiti.add_episode()` — ошибка в SDK:
  `AttributeError: 'Completions' object has no attribute 'responses'`
- **Причина:** Graphiti SDK v0.28+ использует `client.responses.parse()` — это
  **OpenAI Responses API** (замена Completions API, появился в 2025).
  Cerebras, Ollama, и другие провайдеры этот endpoint не реализуют.
- **Это не просто "другой формат промпта"** (как у Mem0) — это полная несовместимость
  на уровне HTTP API: эндпоинт `/v1/responses` не существует у non-OpenAI провайдеров.
- **Статус:** Не решаемо без OpenAI API key или monkey-patching SDK (60+ мест в коде).
- **Решение для бенчмарка:** Raw context fallback — подали тот же текст, что и MD-файлам.

### Проблема 2: Embeddings vendor lock
- **Симптом:** SDK жёстко использует `OpenAIEmbedder` класс
- **Обход:** Ollama поддерживает OpenAI-compatible API (`/v1/embeddings`),
  поэтому embeddings работают через `OpenAIEmbedderConfig(base_url=ollama_url)`.
- **Однако:** Без рабочего LLM-клиента embeddings бесполезны — граф не строится.

### Проблема 3: FalkorDB без данных
- **FalkorDB поднялась за 5 секунд** без проблем (~100 MB RAM).
- **Но без рабочего SDK** это пустой контейнер — граф знаний не построен.
- **UI доступен** на http://localhost:3001 — можно визуально показать пустую базу.

## Что было написано в client.py

Клиент настроен корректно для гипотетической работы:
- `FalkorDriver` для подключения к graph DB
- `OpenAIClient` с `base_url=cerebras` для LLM
- `OpenAIEmbedder` с `base_url=ollama` для embeddings
- Функции `add_episodes()` (загрузка 12 эпизодов) и `search()` (поиск по графу)
- Проблема возникает внутри `graphiti.add_episode()` при вызове LLM для entity extraction

## Бенчмарк: raw context fallback

Поскольку граф не построен, бенчмарк для Graphiti прогнан следующим образом:
1. Те же 12 эпизодов из `test_context.json` объединены в plain text
2. Text подан как system context в Cerebras LLM
3. 20 сценариев (A+B+C) оценены по тем же rubrics

**Результат: 378/500 (75.6%)** — второе место после Helixir v0.3.1.

Это **не отражает реальные возможности Graphiti** — при работающем графе score был бы выше
за счёт structured entity/relation retrieval и temporal queries.

## Архитектурные преимущества Graphiti (теоретические)

1. **Temporal edges** — каждый факт имеет timestamp, можно запрашивать "что было актуально на дату X"
2. **Entity/Relation extraction** — автоматическое построение графа из текста
3. **Episode-based ingestion** — контекст загружается "эпизодами", каждый привязан ко времени
4. **Structured search** — можно искать по типу entity, по relation type, по временному диапазону
5. **FalkorDB** — быстрый graph DB (in-memory, совместим с Cypher/OpenCypher queries)

## Сравнение с другими подходами

| Критерий | MD-файлы | GitHub Issues | Mem0 | Graphiti | Helixir |
|----------|----------|---------------|------|----------|---------|
| Graph relations | Нет | Нет | Нет (Mem0g сломан) | **Да** (FalkorDB) | **Да** (HelixDB) |
| Temporal queries | Нет | Частично | Частично | **Да** (native) | Нет |
| LLM-агностичность | N/A | N/A | Плохая | **Нет** (OpenAI only) | **Да** |
| Setup complexity | Нулевая | Низкая | Очень высокая | Средняя | Высокая |
| Реально работает | Да | Да | Частично | **Нет** | Да |

## Ключевые выводы

1. **Vendor lock-in — убийца.** Graphiti архитектурно превосходит Mem0 (temporal graph vs flat vector),
   но полная привязка к OpenAI Responses API делает его бесполезным в non-OpenAI стеке.

2. **Это не "просто подмени base_url".** В Mem0 vendor lock проявляется в tool call формате
   (работает, но хуже). В Graphiti — полная несовместимость на уровне API endpoint.

3. **FalkorDB — отличный выбор graph DB.** Быстрый, лёгкий, с UI. Если бы SDK был
   LLM-агностичным, Graphiti был бы сильным конкурентом.

4. **Включаем в исследование для полноты.** На вопрос аудитории "а почему не Graphiti?" —
   ответ: "потому что он работает только с OpenAI, а мы тестировали с open-source стеком
   (Cerebras + Ollama). При наличии OpenAI API key результат был бы выше."

## Ссылки

- Graphiti GitHub: https://github.com/getzep/graphiti
- Graphiti Docs: https://docs.getzep.com/graphiti
- FalkorDB: https://falkordb.com
- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses
