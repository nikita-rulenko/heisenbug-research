# Лидеры inference-провайдеров (апрель 2026)

> Сайд-ресерч для доклада: **«где брать токены»** — сравнение популярных inference-платформ по 4 осям: скорость, цена, объём, качество.
>
> Собрано 2026-04-23. Источники — публичные страницы вендоров + artificialanalysis.ai + OpenRouter-статистика.

## TL;DR — 4 категорийных лидера

| Провайдер | Флагман | Сильная сторона | Ключевая цифра |
|---|---|---|---:|
| **Cerebras** | gpt-oss 120B | 🔵 скорость | **3 000 tok/s** |
| **DeepSeek** | DeepSeek R1 | 🟢 цена | **$0.55 / 1M** input |
| **Qwen (Alibaba)** | Qwen3.6 Plus | 🟡 объём | **1.4 T токенов/день** |
| **Anthropic** | Claude Opus 4.7 | 🔴 качество | **87.6%** SWE-bench Verified |

Каждый — ясный лидер ровно в одной категории. Для слайда доклада взяли именно эту квадру: одна ось = один провайдер, без overlap'ов.

---

## Полная сравнительная таблица

Пять «громких» провайдеров плюс референсные OpenAI/Anthropic. Цифры — флагманская модель каждого провайдера на апрель 2026.

| Провайдер | Флагман модель | Скорость (tok/s) | Input $/1M | Output $/1M | Volume-milestone | Примечания |
|---|---|---:|---:|---:|---|---|
| **Cerebras** | gpt-oss 120B | **3 000**&nbsp;⚡ | $0.25 | $0.69 | 1M tokens/day free tier | Wafer-scale; 969 tok/s на Llama 3.1 405B, 2 700+ на gpt-oss 120B |
| **Cerebras** | Llama 3.1 405B | 969 | $6.00 | $12.00 | — | Фронтировая модель |
| **Groq** | Llama 3.3 70B | 300–1 200 (420) | $0.59 | $0.79 | 50% batch discount | LPU, runner-up по скорости |
| **SambaNova** | Llama 3.1 405B | 132 | $5.00 | $10.00 | Native FP16 | RDU-чипы, 8K ctx cap |
| **Together AI** | Llama 4 Maverick | ~400 | $0.27 | $0.27 | 4× vLLM throughput | Breadth of open models |
| **Fireworks AI** | Llama 3.3 70B | 145 | $0.90 | $0.90 | Sub-200ms TTFT at scale | «Reliability + DX» лидер |
| **DeepSeek** | DeepSeek R1 | ~60 | **$0.55**&nbsp;💰 | $2.19 | 90% cache discount → $0.03/M | Reasoning-класс за копейки |
| **Alibaba / Qwen** | Qwen3.6 Plus | ~180 | $0.29 | $1.10 | **1.4 T токенов/день** 📦 | #1 по объёму на OpenRouter (+711% за период) |
| **OpenAI** | GPT-5.2 | ~120 | $1.75 | $14.00 | Премиум baseline | |
| **Anthropic** | Claude Opus 4.7 | ~70 | $5.00 | $25.00 | 90% prompt-cache discount | **87.6% SWE-bench** 🎯 — #1 качество |

---

## Лидеры по осям

### ⚡ Скорость — Cerebras
**3 000 tok/s** на gpt-oss 120B ([Cerebras blog — 2026 Insights](https://www.cerebras.ai/blog/2026Insights)).

Wafer-scale архитектура даёт 5–20× к GPU-провайдерам на одинаковых моделях. Верифицированные цифры:
- Llama 3.1 8B — 1 800 tok/s
- Llama 3.3 70B — 2 314 tok/s
- Llama 3.1 405B — 969 tok/s
- gpt-oss 120B — **3 000+ tok/s**
- Qwen3 Coder 480B — 2 000 tok/s

Runner-up: **Groq** (LPU, 420 tok/s на 70B, пики до 1 200).

### 💰 Цена — DeepSeek
**$0.55 / $2.19** за 1M input/output ([DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing/)).

DeepSeek R1 — reasoning-модель класса o1/Opus за дробную цену от лидеров. С 90%-скидкой на кеш hit'ы input падает до **$0.03/1M** — практически бесплатно на повторяющихся промтах.

Референс: GPT-5.2 — $14 output, Claude Opus 4.7 — $25 output. R1 дешевле Opus'а **в 11 раз** на выходе.

### 📦 Объём — Qwen (Alibaba)
**1.4 триллиона токенов в сутки** на OpenRouter ([BigGo Finance](https://finance.biggo.com/news/202604070426_Alibaba_Qwen3.6-Plus_AI_Model_Breaks_Daily_Usage_Record)).

Qwen3.6 Plus в апреле 2026 стала **первой моделью в мире**, пересекшей триллион токенов в сутки через единый API-роутер — #1 по использованию глобально, +711% за период. Это та самая новость про «Qwen вышел на триллион», с которой начали ресерч.

### 🎯 Качество — Anthropic Claude Opus 4.7
**87.6%** на SWE-bench Verified ([TokenMix blog](https://tokenmix.ai/blog/swe-bench-2026-claude-opus-4-7-wins)).

Релиз 16 апреля 2026. Лидер по 7 major-бенчмаркам на момент выхода:
- SWE-bench Verified — **87.6%** (vs GPT-5.3 Codex 85.0%, Gemini 3.1 Pro 80.6%)
- SWE-bench Pro — **64.3%**
- Рост с Opus 4.6: +6.8pp на Verified

1M context, Mythos Safety Layer, `/ultrareview`. Премиальный baseline — на чём запускать когда точность важнее цены.

---

## Методологические замечания

1. **Скорость — пиковая, не средняя.** Cerebras 3 000 tok/s — на gpt-oss 120B в идеальных условиях (короткий prompt, длинный output). На длинных контекстах throughput падает.

2. **Цена — для флагмана.** Большинство провайдеров хостят дешёвые модели (Qwen, Llama small, Mistral) за центы. Здесь сравниваем «сопоставимый класс» — flagship/frontier модель каждого.

3. **Объём — как проксь популярности.** 1.4T токенов/день измеряется на OpenRouter; прямые корпоративные клиенты Anthropic/OpenAI считаются отдельно и не попадают в эту метрику. Реальный объём OpenAI/Anthropic, вероятно, ещё больше, но не публичен.

4. **Качество ≠ SWE-bench.** 87.6% на coding-задачах не значит, что Opus 4.7 лидер везде. На reasoning (AIME, GPQA) картина может быть другой. Для доклада взяли именно SWE-bench как прокси «качество для разработчиков».

5. **Бенчмарки обновляются.** Цифры — на **2026-04-23**. Cerebras подтянет скорость, DeepSeek удешевит R1.5, Qwen/Alibaba выпустит новую модель — таблица должна быть пересобрана к моменту доклада.

---

## Почему это важно для основного ресерча

Бенчмарки подходов к памяти (v2/v3, Context Recovery, Test-Writing) **все запущены на Cerebras** (gpt-oss-120B). Почему это правильный выбор:

- **Скорость убирает bottleneck модели.** Мы меряем *подход к памяти*, а не латентность inference. Fast LLM = чистый изолированный эксперимент.
- **Цена позволяет прогонять много раз.** 3 прогона × 4 подхода × 3 части × Context Recovery + Test-Writing = сотни запусков в пределах $10.
- **Free tier (1M/день) даёт предсказуемый бюджет** на репетиции доклада.

Если бы делали бенчмарк сегодня **для продакшена** — выбор зависит от сценария:
- Нужен reasoning дёшево → **DeepSeek R1**
- Нужна скорость ответа для live-UX → **Cerebras** или **Groq**
- Нужно максимум качества (код-ревью, архитектура) → **Claude Opus 4.7**
- Нужен масштаб и экосистема → **Qwen / Alibaba Cloud**

Для доклада это — подтекст: **инфраструктура inference уже решена, узкое место переехало в память и контекст.** То есть именно в тот слой, который мы сравниваем на v2/v3.

---

## Источники

- [Cerebras — 2026 Insights (fast inference finds its groove)](https://www.cerebras.ai/blog/2026Insights)
- [Cerebras — Llama 3.1 405B at 969 tok/s](https://www.cerebras.ai/blog/llama-405b-inference)
- [Cerebras — Free 1M tokens/day tier](https://adam.holter.com/cerebras-opens-a-free-1m-tokens-per-day-inference-tier-and-ccerebras-now-offers-free-inference-with-1m-tokens-per-day-real-speed-benchmarks-show-2600-tokens-sec-on-llama4scout-here-are-the-actual-n/)
- [Cerebras vs Blackwell benchmark](https://www.cerebras.ai/blog/blackwell-vs-cerebras)
- [Groq Pricing](https://groq.com/pricing)
- [Groq API Pricing 2026 — TokenMix](https://tokenmix.ai/blog/groq-api-pricing)
- [SambaNova — Artificial Analysis](https://artificialanalysis.ai/providers/sambanova)
- [Together Inference Engine 2.0](https://www.together.ai/blog/together-inference-engine-2)
- [Fireworks AI Review 2026](https://tokenmix.ai/blog/fireworks-ai-review)
- [DeepSeek API Pricing Docs](https://api-docs.deepseek.com/quick_start/pricing/)
- [Alibaba Qwen3.6-Plus — 1.4T tokens/day record (BigGo Finance)](https://finance.biggo.com/news/202604070426_Alibaba_Qwen3.6-Plus_AI_Model_Breaks_Daily_Usage_Record)
- [Alibaba_Qwen on X — trillion tokens/day on OpenRouter](https://x.com/Alibaba_Qwen/status/2040242594719158460)
- [SWE-Bench Leaderboard April 2026](https://www.marc0.dev/en/leaderboard)
- [SWE-Bench 2026 — Opus 4.7 wins (TokenMix)](https://tokenmix.ai/blog/swe-bench-2026-claude-opus-4-7-wins)
- [Claude Opus 4.7 Review (Build Fast With AI)](https://www.buildfastwithai.com/blogs/claude-opus-4-7-review-benchmarks-2026)
- [Claude Opus 4.7 Benchmarks — Vellum AI](https://www.vellum.ai/blog/claude-opus-4-7-benchmarks-explained)
- [Claude Opus 4.7 — What's New (Techsy)](https://techsy.io/en/blog/claude-opus-4-7-whats-new)
- [Anthropic Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Tokens per Second Guide 2026 — Morph](https://www.morphllm.com/tokens-per-second)

## Связанные слайды

- `assets/rambler_slides/inference_leaders_slide.html` — визуализация этой таблицы для доклада (4 карточки, цвет по категории).
