# Heisenbug 2026 — Исследование подходов к управлению контекстом AI-агентов

> Материалы к докладу на [Heisenbug 2026](https://heisenbug.ru/talks/8f09764b2d54406981d189ceb30ef032/)

## TL;DR — сводная таблица результатов

Сравниваем **4 подхода** к хранению контекста AI-агентов на одном Go-проекте (637 тестов).
Ниже — лучшее из всех замеров (Q&A на 22 задачах + Context Recovery онбординг).

| Подход | Q&A v3 (точность) | Онбординг: точность | Онбординг: токены | Онбординг: $ | CPR (качество/$) | Сильная сторона |
|---|---:|---:|---:|---:|---:|---|
| **GitHub Issues** | 🥇 **75.9%** | 🥇 **88.8%** | 54,397 | $0.033 | 2,175 | Лучший баланс точности и стоимости |
| **MD-файлы** | 72.7% | 🥇 **88.8%** | 53,195 | $0.032 | 2,225 | Простота, бесплатное обновление |
| **Mem0** | 73.9% | 58.8% ⚠️ | 🥇 **29,638** | 🥇 **$0.018** | 🥇 **2,643** | Дешевле всех; но stale data бьёт по точности |
| **Helixir MCP** | 72.4% | 75.0% | 170,668 ⚠️ | $0.102 ⚠️ | 586 | Граф-рассуждения (Part B 76.2%, Part C 98.8%) |

**Что значат колонки:**
- **Q&A v3** — % правильных ответов на 22 задачи (Part A факты + Part B граф + Part C решения), max 352 балла
- **Онбординг точность** — % правильных ответов на 5 проверочных вопросов после восстановления контекста через MCP
- **Токены/$** — сколько LLM прочитала+сгенерировала и сколько это стоило по тарифу [Cerebras $0.60/M](https://cerebras.ai/pricing)
- **CPR** = Cost-Performance Ratio = качество ÷ стоимость; чем выше — тем больше пользы на доллар

**Главные выводы:**
1. На контексте < 50KB **все 4 подхода работают сопоставимо** (Q&A 72-76%, разница в пределах шума критика).
2. **Семантическая память (Mem0/Helixir) требует обслуживания** — устаревшие факты подаются с высоким confidence (0.83), что хуже их отсутствия. MD/Issues обновляются перезаписью бесплатно.
3. **Helixir выигрывает на reasoning** (Part B 76.2%, Part C 98.8%), но дорог при онбординге (3.2× MD).
4. **GitHub Issues** — единственный подход, у которого качество выросло при масштабировании (+1.4% от v2 к v3).

[Подробный анализ →](docs/results/v3_results.md) · [Дизайн бенчмарка →](docs/methodology/01_design.md) · [Дашборд для live-демо →](benchmarks/context_recovery/dashboard_recovery.html)

---

## Чем это полезно для бизнеса

Если вы выбираете способ хранить контекст для AI-агентов в команде — этот раздел на одну минуту.

- **Для команд до ~50KB документации** (README, AGENTS.md, cursor-rules) **не усложняйте.** Обычные **MD-файлы** или **GitHub Issues** дают ту же точность, что и Mem0/Helixir, но без инфраструктуры, патчей и плат за embeddings. Меньше движущихся частей → меньше [OPEX](https://www.investopedia.com/terms/o/operating_expense.asp) (операционных расходов на поддержку).
- **Семантическая память платит обслуживанием.** Устаревшие факты в Mem0 уронили онбординг с 88.8% до **58.8%** — хуже, чем не иметь памяти вообще. Если внедряете векторную/графовую память — **сразу планируйте процесс инвалидации** (rebuild индекса, update_memory, регулярную ревизию).
- **Helixir выигрывает там, где важно «почему».** Decision reasoning (98.8%) и multi-hop рассуждения (76.2%) — преимущество ровно на тех вопросах, где LLM обычно проседает. Если ваш кейс — анализ архитектурных решений и trade-off'ов, граф-память окупается.
- **Память ≠ умение применять.** Лучший по Q&A (Helixir, 94.2%) написал РАБОЧИЙ тест **хуже**, чем простой MD-подход (49 vs 41 из 52). Богатый контекст подталкивает агента к over-engineering и compile errors. Не оценивайте AI-инструменты только по «помнит ли» — добавляйте «может ли применить».
- **GitHub Issues — единственный подход, видимый команде.** Запись в Mem0/Helixir видна только следующему AI-агенту. Issue-комментарий видят все разработчики. Двойная польза без удвоения усилий.

> **TL;DR:** выбирайте простейший подход, который покрывает ваш масштаб; усложняйте только под конкретный gap.

---

## Содержание

- [TL;DR — сводная таблица результатов](#tldr--сводная-таблица-результатов)
- [Чем это полезно для бизнеса](#чем-это-полезно-для-бизнеса)
- [О чём исследование](#о-чём-исследование)
  - [Как читать результаты](#как-читать-результаты)
- [Этапы бенчмарка — результаты](#этапы-бенчмарка--результаты)
  - [Этап 1: Q&A — что агент помнит (Benchmark v3)](#этап-1-qa--что-агент-помнит-benchmark-v3)
  - [Этап 2: Context Recovery — стоимость онбординга](#этап-2-context-recovery--стоимость-онбординга)
  - [Этап 3: Test-Writing — может ли агент написать рабочий тест](#этап-3-test-writing--может-ли-агент-написать-рабочий-тест)
  - [Сводная разбивка v3 по типам задач](#сводная-разбивка-v3-по-типам-задач)
  - [Какой подход лучше для какого типа задач](#какой-подход-лучше-для-какого-типа-задач)
  - [Ключевые выводы v2+v3](#ключевые-выводы-v2v3)
- [Структура репозитория](#структура-репозитория)
- [Подходы в деталях](#подходы-в-деталях)
  - [1. MD-файлы + Cursor Rules](#1-md-файлы--cursor-rules)
  - [2. GitHub Issues MCP](#2-github-issues-mcp)
  - [3. Mem0 (self-hosted)](#3-mem0-self-hosted)
  - [4. Helixir MCP](#4-helixir-mcp-graph--fastthink--causal-reasoning)
- [Методология бенчмарка](#методология-бенчмарка)
  - [v2 + v3 — три части](#v2--v3--три-части)
  - [Context Recovery Benchmark](#context-recovery-benchmark)
  - [Общий стек](#общий-стек)
- [Методология расчёта стоимости](#методология-расчёта-стоимости)
- [Phase 2 — практическая верификация](#phase-2-практическая-верификация-и-стоимость-обслуживания-2026-04-14)
  - [Стоимость обслуживания по подходам](#стоимость-обслуживания-по-подходам)
  - [Ключевые находки Phase 2](#ключевые-находки-phase-2)
- [Портал Bean & Brew](#портал-bean--brew)
- [Tech Stack исследования](#tech-stack-исследования)
- [Воспроизведение бенчмарков](#воспроизведение-бенчмарков)
  - [Требования](#требования)
  - [Путь 1: Quick start через Makefile (рекомендуется)](#путь-1-quick-start-через-makefile-рекомендуется)
  - [Путь 2: Live UI-дашборд (для презентации)](#путь-2-live-ui-дашборд-для-презентации--ручного-исследования)
  - [Путь 3: Ручной запуск v2-скриптов (advanced)](#путь-3-ручной-запуск-v2-скриптов-advanced)
- [Академические ссылки](#академические-ссылки)
- [Лицензия](#лицензия)

---

## О чём исследование

При работе с AI-агентами (Cursor, Copilot, Cline) ключевая проблема — **деградация контекста**:
агент забывает архитектурные решения, дублирует тесты, путает слои приложения.

Мы **практически** сравнили 4 подхода к хранению и управлению контекстом
на примере Go-портала на 4 уровнях: Unit, Integration, API, UseCase.

### Как читать результаты

Мы задаём AI-агенту **22 задачи** по тестированию реального Go-проекта (637 тестов, 4 слоя архитектуры). Задачи разделены на три части:

| Часть | Что проверяет | Пример задачи | Сценариев | Max баллов |
|-------|--------------|---------------|:---------:|:----------:|
| **Part A** | Факты и retrieval | «Какие тесты покрывают `/api/v1/products`?» | 12 | 192 |
| **Part B** | Граф-рассуждения | «Проследи цепочку зависимостей handler → entity» | 5 | 80 |
| **Part C** | Decision reasoning | «Почему выбрали SQLite, а не PostgreSQL?» | 5 | 80 |
| | | **Итого** | **22** | **352** |

Каждый ответ оценивает **отдельная LLM-модель** (не та, что отвечала) по 4 критериям: accuracy, completeness, context utilization, actionability. Шкала 1-4 на критерий, **max 16 баллов за задачу**. Три прогона, берём медиану. Процент = доля от максимума 352. [**Как и почему мы сделали бенчмарк именно таким** →](docs/methodology/01_design.md) (эволюция v0→v2, все 22 сценария с обоснованиями, ограничения). [**Как устроена оценка в деталях (все 22 вопроса + eval-промт)** →](docs/methodology/02_how_it_works.md)

---

## Этапы бенчмарка — результаты

Бенчмарк состоит из **трёх независимых этапов**, каждый отвечает на свой вопрос:

| Этап | Вопрос | Что меряем | Max |
|---|---|---|---|
| **1. Q&A** | Что агент **помнит** из контекста? | Точность ответов на 22 задачи (Part A/B/C) | 352 |
| **2. Context Recovery** | Сколько **стоит** восстановить контекст? | Токены, $, время онбординга + 5 контрольных вопросов | $/% |
| **3. Test-Writing** | Может ли агент **применить** запомненное к коду? | Реальный `go test` написанного теста + DeepSeek-судья | 52 |

Этапы 1 и 2 идут в дашборд для live-демо. Этап 3 — Makefile-only, off-stage.

### Этап 1: Q&A — что агент помнит (Benchmark v3)

> Проект масштабирован с 175 до **637 тестов** (29KB контекст). Mem0 и Helixir хранят устаревшие данные.

| # | Подход | v2 (175 тестов) | v3 (637 тестов) | Delta |
|---|--------|:--------------:|:--------------:|:-----:|
| 1 | **GitHub Issues** MCP | 262 (74.4%) | **267 (75.9%)** | **+1.4%** |
| 2 | **Mem0** (self-hosted) | **266 (75.6%)** | 260 (73.9%) | -1.7% |
| 3 | **MD-файлы** (.cursor/rules) | 265 (75.3%) | 256 (72.7%) | -2.6% |
| 4 | **Helixir MCP** (full tools) | 265 (75.3%) | 255 (72.4%) | **-2.8%** |

> 💡 Например: GitHub Issues набрал 267 из 352 возможных баллов = 75.9%. Это значит, что агент с контекстом из GitHub Issues в среднем выдаёт ответы на ¾ от идеала по всем 22 задачам.

### Этап 2: Context Recovery — стоимость онбординга

Отдельный бенчмарк: сколько **токенов и денег** тратит агент, чтобы "вспомнить" проект через каждый источник контекста. Двухфазный: сначала загрузка контекста, затем 5 проверочных вопросов. Accuracy = доля правильных ответов на проверочные вопросы.

> **Главная находка v3**: семантическая память требует обслуживания. Устаревшие данные = потеря accuracy.

| Подход | Accuracy | Токены | Стоимость | CPR |
|--------|:--------:|-------:|----------:|----:|
| **MD files** | **88.8%** | 53,195 | $0.032 | 2,225 |
| **GitHub Issues** | **88.8%** | 54,397 | $0.033 | 2,175 |
| **Helixir MCP** | 75.0% | 170,668 | $0.102 | 586 |
| **Mem0** | 58.8% | 29,638 | $0.018 | 2,643 |

> 💡 **Токены** = объём текста, который LLM прочитала и сгенерировала. **Стоимость** = цена в долларах по [тарифу Cerebras](#методология-расчёта-стоимости). **CPR** (Cost-Performance Ratio) = качество за доллар, чем выше — тем эффективнее. [Методология расчёта →](#методология-расчёта-стоимости)

**Mem0**: accuracy drop **-30pp** (88.8% → 58.8%) — хранит устаревшие "62 теста" вместо 637.
**Helixir**: потратил **3.2x больше** ($0.102 vs $0.032) токенов, но восстановил только 75%.
**MD/Issues**: получают актуальный контекст напрямую — 88.8% accuracy.

### Этап 3: Test-Writing — может ли агент написать рабочий тест

Q&A-точность мерит «помнит ли агент факты». Этот этап мерит **«может ли агент применить запомненное к РЕАЛЬНОМУ коду»** — написать новый Go-тест против существующего метода в портале, который **компилируется и проходит** через `go test`.

**Как устроено.** После онбординга и Q&A агент получает топик (например, «напиши unit-тест для `Order.CalculateTotal` с edge-cases»), пишет Go-файл прямо в `coffee-portal/internal/<pkg>/zz_bench_*_test.go`. Мы запускаем `go test ./...`, независимый судья (**DeepSeek** — другая модельная семья, чтобы убрать bias) оценивает результат. После каждого топика — полный rollback портала.

Три режима топиков:
- **fixed** — `Order.CalculateTotal` для всех 4 подходов → прямое сравнение
- **wide** — рандом из 5-топикового пула, seed=`hash(approach)` → воспроизводимо, без cherry-pick
- **free** — агент САМ выбирает метод. Самый интересный режим: мерит не «помнит ли», а «адекватен ли в принятии решений»

Критерии судьи (1-4 каждый): `fact_grounding` (использует ли реальные сущности), `convention_match` (соблюдает naming + table-driven), `coverage_depth` (глубина edge-cases), `runs_clean` (компилируется и проходит). Для free — ещё `target_choice` (насколько неочевиден выбор). Отдельно — `divergence` (0-4): сколько НЕсуществующих сущностей выдумано.

#### Результаты (один прогон, 2026-04-20)

| Подход | fixed (16) | wide (16) | free (20) | **Σ (52)** | Divergence |
|---|:---:|:---:|:---:|:---:|:---:|
| **MD-файлы** | 15 | 15 | **19** | **49** | 0 / 0 / 0 |
| **GitHub Issues** | **16** | **16** | 17 | **49** | 0 / 0 / 0 |
| **Helixir MCP** | 15 | 9 ❌ | 17 | 41 | 0 / 2 / 0 |
| **Mem0** | 15 | 9 ❌ | 12 ❌ | 36 | 0 / 4 / 1 |

❌ = `go test` не прошёл (compile error / fail). Divergence = выдуманные сущности.

#### Что это значит на простом языке

- **Простые подходы (MD, Issues) обогнали богатые (Helixir, Mem0)** на задаче «напиши тест». Парадокс: агент с лучшим Q&A (Helixir, 94.2%) написал РАБОЧИЙ тест хуже, чем агент с MD-файлами (Q&A 90%).
- **Причина — перфекционизм.** Богатый контекст подсказал покрыть CJK-символы (китайские/японские/корейские иероглифы) и emoji на границе `maxRunes`. Агент попытался — и сломал компиляцию (например, сравнил `float64` с `nil`). Бедный контекст → тривиальные но рабочие тесты.
- **Mem0 — слабее всех:** divergence=4 на wide-топике (выдумал половину сущностей), 36/52 итого.
- **Free-режим (агент сам выбирает) — Helixir догнал MD.** Когда есть свобода выбора, граф-память помогает найти неочевидный gap (Helixir выбрал `Product.ApplyDiscount`, MD — `NewsItem.Summary`).

> **Главный инсайт:** контекст-системы должны мерить не только «сколько помнит», а ещё «насколько адекватно применяет». Эта стадия и есть тот разрыв.

#### Запуск (не идёт в дашборд — Makefile-only)

```bash
cd benchmarks/context_recovery
make bench-tw                              # все 4 × TOPIC=both (fixed+wide)
make bench-tw TOPIC=all                    # все 4 × все 3 топика
make bench-tw-approach APPROACH=helixir_mcp TOPIC=free
make bench-full TOPIC=all                  # bench (Q&A) + bench-tw, всё за раз
```

**[Полный дизайн, trade-offs и ограничения →](docs/methodology/05_test_writing_design.md)** · [Сырые результаты →](benchmarks/context_recovery/results/test_writing/)

### Сводная разбивка v3 по типам задач

| Подход | Part A — факты (192) | Part B — граф (80) | Part C — решения (80) | Total |
|--------|:-------------------:|:-----------------:|:--------------------:|:-----:|
| **GitHub Issues** | 135 (70.3%) | 57 (71.2%) | 75 (93.8%) | **267** |
| **Mem0** | 126 (65.6%) | 55 (68.8%) | 79 (98.8%) | **260** |
| **MD files** | 121 (63.0%) | 59 (73.8%) | 76 (95.0%) | **256** |
| **Helixir MCP** | 115 (59.9%) | 61 (76.2%) | 79 (98.8%) | **255** |

### Какой подход лучше для какого типа задач

| Тип задачи | Лидер v3 | Почему | Стоимость (онбординг) |
|------------|---------|--------|----------------------|
| **Фактуальные вопросы** (Part A) | GitHub Issues (70.3%) | Структурированный формат (заголовок+body) лучше индексирует большие объёмы | $0.033 |
| **Граф-рассуждения** (Part B) | Helixir MCP (76.2%) | Каузальные цепочки (IMPLIES/BECAUSE) — прямое преимущество для multi-hop trace | $0.102 |
| **Decision reasoning** (Part C) | Mem0, Helixir (98.8%) | Семантическая память отлично хранит стабильные решения ("почему SQLite?") | $0.018 / $0.102 |
| **Онбординг (Context Recovery)** | MD files (88.8%, $0.032) | Прямой доступ к актуальному тексту, нет stale данных, минимальная стоимость | $0.032 |
| **Cost-efficiency (CPR)** | Mem0 (2,643 quality/cost) | Минимальные токены (29K), но **только если данные актуальны** — иначе 58.8% | $0.018 |
| **Устаревший контекст** | MD files / GitHub Issues | Обновляются перезаписью файла (бесплатно). Mem0/Helixir требуют переиндексации | $0.032-$0.033 |

> **Главный инсайт**: нет одного лучшего подхода. Helixir лидирует в граф-рассуждениях (Part B: 76.2%) и decision reasoning (Part C: 98.8%), но проигрывает на фактуальных вопросах (Part A: 59.9%) из-за устаревших данных с высоким confidence (0.83). GitHub Issues — лучший баланс accuracy/стоимость при актуальном контексте.

### Ключевые выводы v2+v3

1. **На масштабе <50KB контекста (637 тестов, 29KB) подходы выравниваются** (72-76%). Различия в 3.5pp статистически незначимы при stddev 7-15.

2. **Семантическая память (Mem0, Helixir) требует обслуживания**. Устаревший контекст = деградация accuracy до 58-75%. Это OPEX, невидимый при первоначальной оценке.

3. **MD-файлы обновляются бесплатно** (перезапись файла). Mem0/Helixir требуют переиндексации (~30+ API calls к embedding).

4. **GitHub Issues показали рост** (+1.4%) — формат "заголовок + body" лучше структурирует большие объёмы.

5. **Для реального расхождения** нужен контекст 200K+ chars (~50K+ tokens) — чтобы не помещался в context window.

| Масштаб | Контекст | Рекомендация |
|---------|----------|-------------|
| **< 50KB** (~12K tok) | Всё в окне | MD files (бесплатно, просто) |
| **50-200KB** | На грани | GitHub Issues + поиск |
| **200-500KB** | Не влезает | Mem0 / Helixir (если обновлены!) |
| **>500KB** | Enterprise | Helixir (каузальный граф) |

[Подробный анализ v3](docs/results/v3_results.md)

<details>
<summary>Benchmark v2 — базовая таблица (175 тестов)</summary>

> Generator: gpt-oss-120b -> Evaluator: zai-glm-4.7 | Шкала 1-4 | 3 прогона, медиана

| # | Подход | Part A (192) | Part B (80) | Part C (80) | **Итого** | **%** |
|---|--------|:------------:|:-----------:|:-----------:|:---------:|:-----:|
| 1 | **Mem0** | 125 | 62 | 79 | **266** | **75.6%** |
| 2 | **Helixir MCP** | 124 | 63 | 78 | **265** | **75.3%** |
| 2 | **MD-файлы** | 123 | 62 | 80 | **265** | **75.3%** |
| 4 | **GitHub Issues** | 122 | 60 | 80 | **262** | **74.4%** |

</details>

## Структура репозитория

```
heisenbug-research/
├── docs/                          # Документация исследования
│   ├── background/                #   Обзор литературы и анализ фреймворков
│   ├── experiments/               #   Описание каждого эксперимента
│   ├── benchmark/                 #   Дизайн, результаты, context recovery
│   └── notes/                     #   Рабочие заметки
│
├── benchmark/                     # Код бенчмарка
│   ├── scripts/                   #   Python-скрипты (v2 runner, part_b, part_c, helixir_mcp, context_recovery)
│   ├── data/                      #   Контекстные данные (29 эпизодов, 5 решений)
│   └── results/                   #   JSON-результаты v2 + v3 (36 файлов)
│
├── infra/                         # Инфраструктура
│   ├── mem0/                      #   Docker + patched FastAPI server
│   ├── helixir-local/             #   HelixDB + helix.toml
│   └── mcp/                       #   MCP-серверы (mem0_mcp_server.py)
│
├── scripts/                       # Утилиты
│   ├── dashboard_recovery.html    #   Веб-дашборд для конференции (live demo)
│   ├── demo_live.sh               #   Скрипт живого демо
│   ├── generate_pptx.py           #   Генерация слайдов
│   └── render_*.py                #   Рендеринг таблиц (PNG)
│
├── assets/                        # Визуальные материалы
│   ├── diagrams/                  #   D2-диаграммы (src + rendered SVG/PNG)
│   └── tables/                    #   Сравнительные таблицы (PNG)
│
└── presentation/                  # Слайды доклада
```

## Подходы в деталях

### 1. MD-файлы + Cursor Rules

Самый простой подход — контекст хранится в `.cursor/rules/*.mdc` и `AGENTS.md`.

- **Плюсы**: нулевой setup, нет зависимостей, работает из коробки, обновление бесплатно
- **Минусы**: flat text не масштабируется, не видит противоречий, LLM путается при большом контексте
- **v2**: 265/352 (75.3%) — стабильный baseline с минимальной дисперсией (σ=2.08 на Part A)
- **v3**: 256/352 (72.7%, **-2.6%**) — падение на фактах (Part A: 63.0%), стабилен на решениях (Part C: 95.0%)
- **Онбординг**: 53K токенов, $0.032, accuracy 88.8%
- [Подробнее](docs/experiments/13_experiment_md_files.md)

### 2. GitHub Issues MCP

Структурированные задачи через GitHub Issues API.

- **Плюсы**: привычный формат, labels для категоризации, интеграция с workflow
- **Минусы**: нет семантического поиска, ручная структуризация
- **v2**: 262/352 (74.4%)
- **v3**: 267/352 (75.9%, **+1.4%**) — единственный подход с ростом при масштабировании. Лидер Part A (70.3%)
- **Онбординг**: 54K токенов, $0.033, accuracy 88.8%
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)
- [Подробнее](docs/experiments/14_experiment_github_issues.md)

### 3. Mem0 (self-hosted)

Семантическая память поверх PostgreSQL + pgvector.

- **Плюсы**: семантический поиск (p50=101ms), автоматическое извлечение фактов, лучший CPR (2,643)
- **Минусы**: 6 патчей для работы с Cerebras, vendor lock на OpenAI tool calls, dependency hell
- **v2**: 266/352 (75.6%) — лидер v2
- **v3**: 260/352 (73.9%, **-1.7%**) — устаревшие "62 теста" снижают Part A (65.6%). Но лидер Part C (98.8%)
- **Онбординг**: 29K токенов (самый экономный!), $0.018, но accuracy **58.8%** (stale data)
- [Подробнее](docs/experiments/15_experiment_mem0.md)

### 4. Helixir MCP (graph + FastThink + causal reasoning)

Графовая память поверх HelixDB с каузальным графом и MCP-инструментами.

- **MCP tools**: `search_memory` + `search_reasoning_chain` (IMPLIES/BECAUSE) + `search_by_concept`
- **Плюсы**: готовые reasoning structures для LLM, работает с Cerebras + Ollama, нет vendor lock
- **Минусы**: ранняя стадия, extraction теряет ~25% контента, нет механизма инвалидации stale данных
- **v2**: 265/352 (75.3%) — 2-е место, стабильно 15-16/16 на «почему?»-вопросах
- **v3**: 255/352 (72.4%, **-2.8%**) — **лидер Part B** (76.2%, граф-рассуждения), но провал Part A (59.9%) из-за stale фактов с confidence 0.83
- **Онбординг**: 170K токенов (3.2x дороже), $0.102, accuracy 75.0% — 15 MCP tool calls, 8.8s
- **Ключевая проблема v3**: каузальный граф отлично хранит стабильные решения, но не отслеживает изменяющиеся факты. "32 теста" подаётся с confidence 0.83, что **хуже чем отсутствие данных**
- **Roadmap**: [Проблемы и план](docs/experiments/18_helixir_issues_and_roadmap.md)

## Методология бенчмарка

### v2 + v3 — три части

| Часть | Что проверяет | Max | Сценариев |
|-------|--------------|-----|-----------|
| **A** | Базовые задачи (unit-тест, рефакторинг, impact analysis) | 192 | 12 |
| **B** | Связность фактов (multi-hop, causal chains, contradictions) | 80 | 5 |
| **C** | Decision reasoning (хранение «почему», альтернативы, trade-offs) | 80 | 5 |
| **Итого** | | **352** | **22** |

**Методология v2:**
- **3 прогона** с median/mean/stddev
- **Раздельный evaluator**: Generator (gpt-oss-120b) ≠ Evaluator (GLM 4.7) — устраняет bias self-evaluation
- **Шкала 1-4** (4 критерия: accuracy, completeness, context utilization, actionability)
- v2: 175 тестов (21KB), v3: **637 тестов** (29KB контекст)

### Context Recovery Benchmark

Измеряет **стоимость восстановления контекста** — сколько токенов и времени тратит AI
на onboarding через каждый источник. Двухфазный: Phase 1 (retrieval) → Phase 2 (5 вопросов).
Для live-демо на конференции: split-screen с token-счётчиками.

- [Дизайн и методология](docs/results/context_recovery.md)
- Скрипт: [`benchmarks/context_recovery/runner.py`](benchmarks/context_recovery/runner.py)
- Дашборд: [`benchmarks/context_recovery/dashboard_recovery.html`](benchmarks/context_recovery/dashboard_recovery.html)

### Общий стек

- **LLM (generator)**: Cerebras `gpt-oss-120b`
- **Evaluator (v2)**: Cerebras `zai-glm-4.7` (GLM 4.7 MoE 358B/32B active)
- **Embeddings**: Ollama `nomic-embed-text`

> **Почему Cerebras?** Cerebras — самый быстрый inference-провайдер на рынке (~2000 tok/s output). Для бенчмарка это критично: мы измеряем **скорость извлечения фактов из памяти**, а не латентность модели. Быстрый inference убирает bottleneck LLM и позволяет изолировать влияние именно подхода к контексту. Бонус: низкая цена ($0.60/1M) позволяет делать 3 прогона × 5 подходов × 3 части = 45 запусков без ощутимых расходов.
- [Дизайн бенчмарка](docs/methodology/01_design.md)
- [Как устроена оценка (все 22 вопроса + eval-промт)](docs/methodology/02_how_it_works.md)
- [Полные результаты v2](docs/results/v2_results.md)
- [Полные результаты v3](docs/results/v3_results.md)
- [Phase 4 plan — честность бенчмарка и v4](docs/methodology/03_phase4_plan.md)

### Методология расчёта стоимости

Все стоимости рассчитаны по **публичному тарифу Cerebras Inference API** (март 2026):

| Параметр | Значение | Источник |
|----------|---------|----------|
| Input tokens | **$0.60 / 1M tokens** | [cerebras.ai/pricing](https://cerebras.ai/pricing) |
| Output tokens | **$0.60 / 1M tokens** | [cerebras.ai/pricing](https://cerebras.ai/pricing) |
| Embedding (Ollama) | **$0.00** (локально) | Self-hosted nomic-embed-text |
| MCP tool calls | **$0.00** (локально) | Helixir/Mem0 self-hosted |

**Формула расчёта стоимости онбординга:**

```
cost_usd = (input_tokens × 0.60 + output_tokens × 0.60) / 1,000,000
```

Где:
- `input_tokens` = context_tokens (загрузка контекста) + verification_input_tokens (5 вопросов)
- `output_tokens` = verification_output_tokens (ответы модели)
- Для Helixir MCP: input_tokens включают overhead от 15 tool_call циклов (request→response)

**CPR (Cost-Performance Ratio):**

```
CPR = median_quality_score / cost_usd
```

Чем выше CPR — тем больше качества за доллар. Mem0 лидирует по CPR (2,643) за счёт минимальных токенов (29K), но **только при актуальных данных**.

> ⚠️ Стоимость обновления памяти (Mem0: ~30 API calls к embedding, Helixir: rebuild графа) **не включена** в расчёт, т.к. зависит от частоты изменений проекта. Это скрытый OPEX, описанный в [анализе v3](docs/results/v3_results.md#3-стоимость-обновления-памяти--скрытый-расход).

## Phase 2: Практическая верификация и стоимость обслуживания (2026-04-14)

После бенчмарков мы масштабировали проект (62→336 функций, ~637 прогонов) и проверили
каждый подход на практике — обновление данных, онбординг нового агента, исправление ошибок.

### Стоимость обслуживания по подходам

| Подход | Обновление данных | Сложность | Результат |
|--------|------------------|-----------|-----------|
| **MD-файлы** | Ручное: обновить числа, даты, добавить файлы | Низкая, но OPEX на людях | ✅ Всё обновлено, агент верифицировал |
| **GitHub Issues** | По ходу работы: комменты, чекбоксы, закрытие | **Самая низкая** | ✅ #1-7 закрыты, #10-14 созданы |
| **Mem0** | delete + add_memory, дедупликация блокирует | **Высокая, непредсказуемая** | ⚠️ Часть записей не сохранилась |
| **Helixir** | update_memory + FastThink chains | Средняя (сессии таймаутятся) | ✅ Данные обновлены, цепочка создана |

### Ключевые находки Phase 2

1. **Ложный факт в Mem0** — запись `7fb83211` утверждает, что TestIntegrationProductSearch
   «shares the in-memory database with other tests». В реальности каждый тест изолирован
   через `setupTestDB()` → отдельная `:memory:`. LLM неверно интерпретировал контекст
   при первичном извлечении. Исправить невозможно: `add_memory` возвращает «Added 0 memories»
   (дедупликация), а `update_memory` отсутствует в MCP. Ложный факт с неплохим similarity score
   будет возвращаться при каждом поиске.

2. **Helixir update_memory работает** — эквивалентный ложный факт (`mem_a5945016b15a`)
   был исправлен через `update_memory`. Helixir — единственный подход с семантической памятью,
   где возможна коррекция ошибок без delete+recreate.

3. **FastThink сессии таймаутятся** — между сообщениями в чате сессия может истечь.
   `think_conclude` возвращает «Session not found». Требуется создание новой сессии.
   Рекомендация: выполнять весь цикл think_start→conclude→commit в одном сообщении.

4. **Issues — единственный подход, видимый команде** — комментарий в Issue #14 виден
   всем разработчикам. Обновление записи в Mem0/Helixir видно только следующему AI-агенту.

5. **Онбординговые промты** — созданы 4 стандартизированных промта (XML-структура, роль,
   верификация, пример) для воспроизводимого сравнения подходов. Тестирование в Cursor
   подтвердило корректность всех 4 подходов при актуальных данных.

[Подробный отчёт о верификации](docs/experiments/21_practical_verification.md)

## Портал Bean & Brew

Go-портал (кофейный магазин) — демо-приложение для исследования:

- **Stack**: Go 1.25 + Chi + HTMX + SQLite + Clean Architecture
- **Тесты**: 336 функций (~637 прогонов в `go test -v`) — Entity (237), Handler (179), UseCase (127), Repository (94)
- **Документация**: AGENTS.md + 4 docs + 5 cursor rules + 4 onboarding prompts (всё на русском)
- **Репозиторий**: [heisenbug-coffee-portal](https://github.com/nikita-rulenko/heisenbug-coffee-portal)

## Tech Stack исследования

| Компонент | Технология | Ссылка |
|-----------|-----------|--------|
| Portal | Go 1.25, chi/v5, HTMX 2.0, SQLite | [go-chi/chi](https://github.com/go-chi/chi) |
| LLM | Cerebras gpt-oss-120b | [cerebras.ai](https://cerebras.ai/) |
| Evaluator | Cerebras zai-glm-4.7 | [cerebras.ai](https://cerebras.ai/) |
| Embeddings | Ollama + nomic-embed-text | [ollama.com](https://ollama.com/) |
| Mem0 | mem0ai/mem0 (self-hosted) | [github.com/mem0ai/mem0](https://github.com/mem0ai/mem0) |
| Helixir | nikita-rulenko/Helixir + HelixDB | [github.com/nikita-rulenko/Helixir](https://github.com/nikita-rulenko/Helixir) |
| HelixDB | helixdb/helix-db | [github.com/helixdb/helix-db](https://github.com/helixdb/helix-db) |
| GitHub MCP | github/github-mcp-server | [github.com/github/github-mcp-server](https://github.com/github/github-mcp-server) |
| Vector Store | pgvector/pgvector (PostgreSQL) | [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) |
| MCP SDK | jlowin/fastmcp | [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) |
| AI IDE | Cursor | [cursor.sh](https://cursor.sh/) |

## Воспроизведение бенчмарков

Есть **три пути** запустить бенчмарк — выбирайте по тому, что вам нужно увидеть.

### Требования

- **Go 1.25+** — для запуска `go test` в портале (нужен только для test-writing-этапа)
- **Python 3.12+** с `httpx` — для скриптов бенчмарка
- **Docker + Docker Compose** — для Mem0 (PostgreSQL + pgvector) и HelixDB
- **Ollama** с моделью `nomic-embed-text` — локальные embeddings
- **API-ключи:**
  - `CEREBRAS_API_KEY` — обязательно (генератор + judge для Q&A)
  - `DEEPSEEK_API_KEY` — обязательно для test-writing-этапа (judge)
  - `GITHUB_TOKEN` — для подхода GitHub Issues
- **Клон портала** — `git clone https://github.com/nikita-rulenko/heisenbug-coffee-portal` рядом с research-репо (по умолчанию ожидается в `~/Downloads/heisenbug-coffee-portal`, override через `PORTAL_DIR`)

```bash
# Подготовка
ollama pull nomic-embed-text
pip install httpx
git clone https://github.com/nikita-rulenko/heisenbug-research
git clone https://github.com/nikita-rulenko/heisenbug-coffee-portal
cp .env.example .env  # вписать ключи
```

### Путь 1: Quick start через Makefile (рекомендуется)

Полный control plane живёт в `benchmarks/context_recovery/Makefile`. Из коробки запускает все 3 этапа, работает с git-rollback'ом портала, проверяет pre-conditions.

```bash
cd benchmarks/context_recovery
make help                                  # все цели + переменные

# ── Q&A + Context Recovery (Этапы 1+2, идут в дашборд) ───────
make bench                                 # все 4 подхода × 3 прогона
make bench-approach APPROACH=helixir_mcp   # один подход

# ── Test-Writing (Этап 3, off-stage) ─────────────────────────
make bench-tw                              # все 4 × TOPIC=both (fixed+wide)
make bench-tw TOPIC=all                    # все 4 × все 3 топика
make bench-tw-approach APPROACH=mem0 TOPIC=free

# ── Всё за раз: Q&A + Context Recovery + Test-Writing ────────
make bench-full TOPIC=all

# ── Безопасность / housekeeping ──────────────────────────────
make portal-status                         # проверить что портал чист
make portal-baseline-tests                 # записать baseline `go test ./...`
make scratch-clean                         # снести leftover zz_bench_* (если упало)
```

**Переменные** (`make X VAR=value`): `APPROACH` (md_files|github_issues|mem0|helixir_mcp), `TOPIC` (fixed|wide|free|both|all), `NUM_RUNS` (default 3), `PORTAL_DIR` (если клон портала не в `~/Downloads/`).

### Путь 2: Live UI-дашборд (для презентации / ручного исследования)

То, что используется на докладе — split-screen с live token-счётчиками, побежавшими ответами LLM, таймингами, deltа между подходами.

```bash
cd benchmarks/context_recovery
make start                                 # запустить SSE-сервер в фоне
# открыть http://127.0.0.1:8765/v2        ← v2 дашборд
# или    http://127.0.0.1:8765/           ← v1 дашборд

make logs                                  # tail server logs
make status                                # порт + pid
make stop                                  # остановить
```

Дашборд переигрывает результаты последнего прогона `bench` с реальными wall-clock задержками — выглядит как живой запуск, но не жжёт API-токены при репетиции.

### Путь 3: Ручной запуск v2-скриптов (advanced)

Если нужен полный контроль над flags и тонкая настройка отдельных частей:

```bash
export CEREBRAS_API_KEY=your-key-here

# Q&A v2 — три части по отдельности
cd benchmarks/v2
python3 runner.py md_files ../shared/data/test_context.json 3
python3 part_b.py md_files ../shared/data/test_context.json 3
python3 part_c.py md_files ../shared/data/test_context.json 3

# Helixir MCP (требует запущенный HelixDB + Ollama)
python3 helixir_mcp.py A 3
python3 helixir_mcp.py B 3
python3 helixir_mcp.py C 3

# Context Recovery — обходит Makefile
cd ../context_recovery
python3 runner.py all --num-runs 3
python3 runner.py helixir_mcp --num-runs 3 --with-test-writing --topics all
```

Подробная инструкция по каждому подходу — в соответствующих файлах [`docs/experiments/`](docs/experiments/). Дизайн test-writing-этапа и trade-offs: [`docs/methodology/05_test_writing_design.md`](docs/methodology/05_test_writing_design.md).

## Академические ссылки

- **"Beyond the Context Window"** (arXiv:2603.04814): Cost per turn — fact-memory vs long-context LLM
- **Letta Context-Bench**: Cost-performance ratio для LLM memory providers
- **MemoryAgentBench** (arXiv:2507.05257, ICLR 2026): 4 компетенции — retrieval, learning, long-range, forgetting
- **"How Do Coding Agents Spend Your Money?"** (OpenReview): Token consumption SWE-bench analysis
- **CartoGopher**: Code knowledge graph — 20% token savings, 70-95% на comprehension
- **LoCoMo Benchmark**: Long Context Models evaluation — [arxiv.org/abs/2401.17919](https://arxiv.org/abs/2401.17919)
- **RAG Survey**: Retrieval-Augmented Generation — [arxiv.org/abs/2312.10997](https://arxiv.org/abs/2312.10997)

## Лицензия

Материалы исследования предоставляются для образовательных и научных целей.
