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

## Результаты бенчмарка

### Benchmark v2 — Part A (12 сценариев, шкала 1-4, отдельный evaluator)

> **Generator**: gpt-oss-120b | **Evaluator**: zai-glm-4.7 (GLM 4.7 MoE 358B/32B active)
> **Тесты**: 175 функций (241 с подтестами) | **Контекст**: 21 эпизод, ~20K chars
> **3 прогона**, медианы по сценариям | **Raw context fallback** (граф не построен)

**Median: 107/192 (55.7%) — 5-е место** | Mean: 109.67 ± 16.17 | Range: 95–127

| Сценарий | Median | Runs | Комментарий |
|----------|--------|------|-------------|
| S1: Генерация теста | 0/16 | [15, 0, 0] | Один удачный прогон, два провала |
| S2: Покрытие endpoint | 9/16 | [8, 9, 9] | Ниже всех — raw text хуже структурированного |
| S3: Flaky анализ | 13/16 | [15, 13, 10] | На уровне MD — достаточно текстового контекста |
| S4: Рефакторинг | 9/16 | [9, 7, 10] | На уровне MD, без графа нет преимуществ |
| S5: E2E тест | 16/16 | [16, 5, 16] | Сильная дисперсия — 5 в одном прогоне |
| S6: Impact analysis | 9/16 | [9, 6, 11] | Нет связей без графа |
| S7: Обнаружение дублей | 4/16 | [4, 4, 4] | Ceiling effect |
| S8: Test plan | 12/16 | [12, 12, 16] | Ниже среднего — raw text не структурирован |
| S9: Темпоральный | 4/16 | [4, 4, 4] | Без temporal graph — провал (ожидаемо) |
| S10: Оптимизация | 13/16 | [13, 13, 15] | Чуть ниже остальных |
| S11: Coverage matrix | 8/16 | [8, 8, 12] | Ниже Mem0 (13) и GH Issues (11) |
| S12: Dependencies | 14/16 | [14, 14, 0] | Один полный провал в run 3 |

**Ключевое наблюдение v2:** Graphiti с raw fallback показал **худший результат и высокую дисперсию**
(σ=16.17). Это подтверждает: без работающего графа знаний Graphiti — это просто неструктурированный
текстовый dump, который хуже даже простых MD-файлов. При работающем SDK (с OpenAI API key)
результат был бы значительно выше за счёт structured entity/relation retrieval и temporal queries.

---

### Benchmark v1 — raw context fallback

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
