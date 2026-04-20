"""Test-writing benchmark stage (Phase 3 — runs AFTER verification).

Pipeline per (approach, topic):
  1. plan       — planner LLM (gpt-oss-120b, Cerebras) writes a Go test
                  for an EXISTING method in coffee-portal, given the
                  onboarding context the approach already produced
  2. write      — save to coffee-portal/internal/<pkg>/zz_bench_<id>_test.go
  3. compile+run — `go test -run TestUnitBench<id> -count=1 -timeout=60s`
                   against the full ./... so collateral breakage in
                   neighbouring tests is detected too
  4. judge      — DeepSeek (deepseek-chat) scores fact_grounding /
                   convention_match / coverage_depth / runs_clean (1-4
                   each) plus a separate divergence score (0-4)
  5. rollback   — `git reset --hard HEAD && git clean -fd` + explicit
                   rm of our `zz_bench_*_test.go` scratch (gitignored,
                   so `git clean -fd` alone skips them)

Output → results/test_writing/<timestamp>.json. NO dashboard SSE events.

Trade-offs (documented in README):
  - We require an EXISTING target method (not a new feature). Otherwise
    the agent would have to write the implementation too and we'd be
    measuring a different skill (TDD vs context recovery).
  - We ALWAYS run the full ./... suite per approach, not just the new
    test. Slower (~30-60s per run) but catches LLM patches breaking
    sibling tests, which is a real failure mode worth surfacing.
  - The portal repo MUST be clean before we start. We commit the
    pre-bench state, run, then `git reset --hard HEAD` after each
    approach. Combined with the .gitignore'd `zz_bench_*_test.go`
    pattern, accidental persistence is double-defended.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx


# ── config ────────────────────────────────────────────────────────────
COFFEE_PORTAL_DIR = Path(
    os.environ.get(
        "COFFEE_PORTAL_DIR",
        str(Path.home() / "Downloads" / "heisenbug-coffee-portal"),
    )
)
GO_MODULE = "github.com/nikita-rulenko/heisenbug-portal"

PLANNER_MODEL = "gpt-oss-120b"     # Cerebras
JUDGE_MODEL   = "deepseek-chat"    # DeepSeek (cheaper, no demo concern)

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

GO_TEST_TIMEOUT_S = 90       # `go test` per-invocation cap
PLANNER_MAX_TOKENS = 3000
JUDGE_MAX_TOKENS   = 2000
CONTEXT_CAP_CHARS  = 12000   # truncate onboarding context for planner prompt

SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SCRIPT_DIR / "results" / "test_writing"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ── topics ────────────────────────────────────────────────────────────
# Constraints applied to every topic:
#   - Target method MUST exist in coffee-portal master (verified manually
#     against internal/entity/*.go before adding to the pool).
#   - Test name MUST be globally unique → we append a per-run hex suffix.
#   - External package (`<pkg>_test`) → black-box, isolated from internal
#     test helpers.
#   - The agent NEVER touches the implementation file.

FIXED_TOPIC = {
    "id": "fixed_order_total",
    "package": "internal/entity",
    "package_name": "entity",
    "target": "Order.CalculateTotal",
    "brief": (
        "Напиши новый unit-тест для метода Order.CalculateTotal. Покрой "
        "edge-cases: пустой Items, item с Quantity=0, item с отрицательной "
        "Price, очень большие quantities, смешанные положительные и нулевые. "
        "Используй table-driven подход через t.Run()."
    ),
    "ground_truth_files": ["internal/entity/order.go"],
}

FREE_TOPIC = {
    # "Free" mode: the agent picks its OWN target method from whatever
    # the onboarding context exposed. We deliberately allow this — the
    # whole point is to surface what each approach lets the agent see
    # and judge as a "real gap worth covering". Subjective by design.
    "id": "free_agent_choice",
    "package": "internal/entity",
    "package_name": "entity",
    "target": "<agent-chosen>",
    "brief": (
        "На основе того, что ты узнал из контекста онбординга, ВЫБЕРИ САМ "
        "один существующий метод из пакета entity (Product / Order / "
        "NewsItem / Category) для которого, по твоему мнению, реально "
        "стоит написать дополнительный unit-тест — реальный gap в покрытии, "
        "а не очевидный кейс, который уже наверняка покрыт. "
        "Напиши осмысленный edge-case или table-driven тест для выбранного "
        "метода. ОБЯЗАТЕЛЬНО: первой строкой файла после `package` — "
        "комментарий `// CHOICE: <Type>.<Method> — <причина выбора в одном "
        "предложении>`."
    ),
    # All entity files — judge needs full picture since we don't know
    # in advance what the agent will pick.
    "ground_truth_files": [
        "internal/entity/order.go",
        "internal/entity/product.go",
        "internal/entity/news.go",
        "internal/entity/category.go",
        "internal/entity/errors.go",
    ],
}

WIDE_POOL = [
    {
        "id": "wide_news_summary_emoji",
        "package": "internal/entity",
        "package_name": "entity",
        "target": "NewsItem.Summary",
        "brief": (
            "Напиши edge-case unit-тест для NewsItem.Summary с emoji и "
            "multi-byte символами (CJK, emoji 4-byte) на границе maxRunes. "
            "Проверь что truncation корректно работает по rune-границам, "
            "а не по байтам. table-driven через t.Run()."
        ),
        "ground_truth_files": ["internal/entity/news.go"],
    },
    {
        "id": "wide_product_discount_boundary",
        "package": "internal/entity",
        "package_name": "entity",
        "target": "Product.ApplyDiscount",
        "brief": (
            "Напиши boundary-тест для Product.ApplyDiscount. Кейсы по percent: "
            "-0.01, 0, 0.01, 49.99, 50, 50.01, 99.99, 100, 100.01. Каждый "
            "должен проверять корректное возвращаемое значение (учитывая "
            "что percent<0 или >100 должен возвращать оригинальную цену). "
            "table-driven через t.Run()."
        ),
        "ground_truth_files": ["internal/entity/product.go"],
    },
    {
        "id": "wide_category_validate_unicode",
        "package": "internal/entity",
        "package_name": "entity",
        "target": "Category.Validate",
        "brief": (
            "Напиши table-driven тест для Category.Validate с unicode/CJK "
            "именами и slug'ами (включая emoji в name, кириллицу, CJK, "
            "пустые поля, очень длинные строки). Каждый кейс должен явно "
            "указывать ожидаемую ошибку (или её отсутствие)."
        ),
        "ground_truth_files": ["internal/entity/category.go", "internal/entity/errors.go"],
    },
    {
        "id": "wide_order_can_cancel_matrix",
        "package": "internal/entity",
        "package_name": "entity",
        "target": "Order.CanCancel",
        "brief": (
            "Напиши тест-матрицу для Order.CanCancel со ВСЕМИ возможными "
            "значениями OrderStatus (включая unknown/empty/несуществующие). "
            "Используй table-driven через t.Run() с отдельным subtest на "
            "каждый статус."
        ),
        "ground_truth_files": ["internal/entity/order.go"],
    },
    {
        "id": "wide_news_validate_combos",
        "package": "internal/entity",
        "package_name": "entity",
        "target": "NewsItem.Validate",
        "brief": (
            "Напиши edge-case unit-тест для NewsItem.Validate. Покрой "
            "комбинации: empty Title, empty Content, оба пустых, очень "
            "длинный Content (>10k символов), unicode Title с emoji, "
            "только пробелы в Title. table-driven через t.Run() с явным "
            "expected error на каждый кейс."
        ),
        "ground_truth_files": ["internal/entity/news.go"],
    },
]


# ── prompts ───────────────────────────────────────────────────────────

PLANNER_PROMPT = """Ты — Senior Go Test Engineer на проекте Bean & Brew (coffee shop, Go 1.25, chi router, in-memory SQLite). Тебе дан КОНТЕКСТ ОНБОРДИНГА — то что ты узнал о проекте через свой источник памяти. На основе ЭТОГО контекста напиши **новый unit-тест на Go**.

# Задача
{brief}

Целевой метод: {target}
Имплементация уже существует в файле {package}/<source>.go — ты её НЕ меняешь, только пишешь тест.

# Жёсткие требования
1. Имя функции теста: TestUnitBench{unique_suffix} (РОВНО так, без вариаций)
2. Пакет: package {package_name}_test (внешний пакет, black-box)
3. Импорты: только стандартная библиотека и "{module}/{package}"
4. table-driven через t.Run() с отдельным subtest на каждый кейс
5. Не выдумывай поля, методы или константы — используй ТОЛЬКО то что узнал из контекста онбординга
6. Тест должен компилироваться и проходить против реальной имплементации

# Формат ответа
Верни ТОЛЬКО исходный код Go-файла, ничего больше. Никаких ```go``` маркеров, никакого текста до или после кода. Первой строкой должен идти `package {package_name}_test`, последней — закрывающая `}}` функции теста.

# Контекст онбординга
{context}
"""


FREE_JUDGE_PROMPT = """Ты — независимый ревьюер Go-тестов. Это режим **FREE** — агенту разрешили САМОМУ выбрать какой метод покрывать тестом. Твоя задача — оценить и качество теста, И качество ВЫБОРА.

В тесте должна быть строка `// CHOICE: <Type>.<Method> — <причина>`. Если её нет — это нарушение convention.

Оцени по 5 критериям (каждый 1-4) + отдельная divergence (0-4). Max = 20.

## Критерии (1-4):
- **fact_grounding**: использует только реально существующие entity/методы/поля? (4 = всё реально, 1 = много выдумок)
- **convention_match**: TestUnitBench... + table-driven + external `_test` package + строка CHOICE в шапке? (4 = всё, 1 = нарушено почти всё)
- **coverage_depth**: покрывает осмысленные edge-cases? (4 = глубоко, 1 = тривиально)
- **runs_clean**: компилируется и проходит? (4 = PASS, 3 = PASS с warnings, 2 = FAIL но логика разумная, 1 = compile error / panic)
- **target_choice**: насколько разумен ВЫБОР метода? Реальный gap или очевидное место где уже наверняка много тестов? (4 = неочевидный осмысленный gap, 3 = разумно но банально, 2 = слабый выбор, 1 = бессмысленный — например уже покрыто 14 subtest'ами)

## Divergence (0-4):
Сколько НЕсуществующих сущностей упомянуто (выдуманные методы/поля/константы/ошибки)? 0 = ни одной выдумки, 4 = больше половины.

## Формат (строгий JSON):
{{
  "chosen_target": "<извлечённый из CHOICE Type.Method, или 'unparseable' если строки нет>",
  "fact_grounding": <1-4>,
  "convention_match": <1-4>,
  "coverage_depth": <1-4>,
  "runs_clean": <1-4>,
  "target_choice": <1-4>,
  "divergence": <0-4>,
  "notes": "<2-3 предложения: оцени и сам выбор, и качество исполнения>"
}}

# Бриф (что предлагали)
{brief}

# Ground truth (все entity-файлы — агент мог выбрать любой)
{ground_truth}

# Что написала LLM
```go
{test_source}
```

# Результат `go test`
exit_code={exit_code}
duration_ms={duration_ms}

stdout (last 2000 chars):
{stdout}

stderr (last 2000 chars):
{stderr}
"""


JUDGE_PROMPT = """Ты — независимый ревьюер Go-тестов. Тебе дано: что просили написать, реальный код (ground truth), что написала LLM, и результат `go test`.

Оцени тест по 4 критериям (каждый 1-4) + отдельная оценка divergence (0-4).

## Критерии (1-4 каждый):
- **fact_grounding**: использует только реально существующие entity/методы/поля? 4 = всё реально, 1 = много выдумок
- **convention_match**: соблюдает naming convention TestUnitBench... + table-driven + external package `_test`? 4 = полностью, 1 = совсем не похоже
- **coverage_depth**: покрывает ли осмысленные edge-cases (boundaries, unicode, negatives, etc)? 4 = глубоко, 1 = тривиально
- **runs_clean**: компилируется и проходит? 4 = PASS, 3 = PASS с warnings, 2 = FAIL но логика разумная, 1 = compile error / panic / неприменимо

## Divergence (0-4):
Сколько НЕсуществующих сущностей упомянуто в тесте (выдуманные методы, поля, константы, ошибки)? 0 = ни одной выдумки, 4 = больше половины.

## Формат ответа (строгий JSON, ничего кроме):
{{
  "fact_grounding": <int 1-4>,
  "convention_match": <int 1-4>,
  "coverage_depth": <int 1-4>,
  "runs_clean": <int 1-4>,
  "divergence": <int 0-4>,
  "notes": "<2-3 предложения: что пошло хорошо/плохо, какие выдумки если есть>"
}}

# Что просили
{brief}

# Ground truth (реальный код имплементации)
{ground_truth}

# Что написала LLM
```go
{test_source}
```

# Результат `go test`
exit_code={exit_code}
duration_ms={duration_ms}

stdout (last 2000 chars):
{stdout}

stderr (last 2000 chars):
{stderr}
"""


# ── data classes ──────────────────────────────────────────────────────

@dataclass
class TopicResult:
    topic_id: str
    target: str
    test_name: str
    test_path: str
    plan_latency_ms: int
    plan_tokens_in: int
    plan_tokens_out: int
    test_source: str
    go_exit_code: int
    go_duration_ms: int
    go_stdout: str
    go_stderr: str
    judge_latency_ms: int
    judge_raw: str
    scores: dict = field(default_factory=dict)


@dataclass
class ApproachResult:
    approach: str
    fixed: TopicResult | None = None
    wide: TopicResult | None = None
    free: TopicResult | None = None


# ── http ──────────────────────────────────────────────────────────────

def _client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        transport=httpx.HTTPTransport(retries=2),
    )


def _call_cerebras(messages: list[dict], model: str, max_tokens: int) -> tuple[str, dict, int]:
    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        raise RuntimeError("CEREBRAS_API_KEY not set")
    payload = {"model": model, "messages": messages, "temperature": 0.2,
               "max_tokens": max_tokens}
    t0 = time.time()
    with _client() as cl:
        resp = cl.post(f"{CEREBRAS_BASE_URL}/chat/completions",
                       headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    resp.raise_for_status()
    latency = int((time.time() - t0) * 1000)
    msg = resp.json()["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("reasoning_content") or "").strip()
    usage = resp.json().get("usage", {})
    return content, usage, latency


def _call_deepseek(messages: list[dict], model: str, max_tokens: int) -> tuple[str, dict, int]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    payload = {"model": model, "messages": messages, "temperature": 0.0,
               "max_tokens": max_tokens}
    t0 = time.time()
    with _client() as cl:
        resp = cl.post(f"{DEEPSEEK_BASE_URL}/chat/completions",
                       headers={"Authorization": f"Bearer {api_key}"}, json=payload)
    resp.raise_for_status()
    latency = int((time.time() - t0) * 1000)
    msg = resp.json()["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    usage = resp.json().get("usage", {})
    return content, usage, latency


# ── helpers ───────────────────────────────────────────────────────────

def _portal_clean_check() -> tuple[bool, str]:
    """Return (is_clean, status_porcelain)."""
    res = subprocess.run(["git", "-C", str(COFFEE_PORTAL_DIR), "status", "--porcelain"],
                         capture_output=True, text=True, timeout=10)
    porc = res.stdout.strip()
    return (porc == "", porc)


def _portal_rollback() -> None:
    """Reset portal to HEAD + sweep our scratch files. SAFE because we
    require a clean tree at start (and commit pre-bench state).

    Note: `git clean -fd` does NOT remove gitignored files, and our
    `zz_bench_*_test.go` pattern IS gitignored — so we must glob+rm
    scratch files explicitly. We deliberately do NOT use `-fdx` to
    avoid nuking unrelated ignored artifacts (build outputs, .env, …).
    """
    subprocess.run(["git", "-C", str(COFFEE_PORTAL_DIR), "reset", "--hard", "HEAD"],
                   capture_output=True, timeout=15, check=False)
    subprocess.run(["git", "-C", str(COFFEE_PORTAL_DIR), "clean", "-fd"],
                   capture_output=True, timeout=15, check=False)
    # Sweep our gitignored scratch files (git clean -fd skips them).
    for stale in (COFFEE_PORTAL_DIR / "internal").rglob("zz_bench_*_test.go"):
        try:
            stale.unlink()
        except OSError:
            pass


def _read_ground_truth(files: list[str]) -> str:
    """Concatenate referenced impl files for the judge."""
    parts = []
    for rel in files:
        p = COFFEE_PORTAL_DIR / rel
        if p.exists():
            parts.append(f"// === {rel} ===\n{p.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)[:8000]  # cap


def _suffix() -> str:
    """Short hex suffix unique per (approach, topic) — Go identifier safe."""
    return secrets.token_hex(4).upper()  # 8 hex chars, ~4B unique


def _strip_code_fence(src: str) -> str:
    """Planner is told NOT to use ```go```, but defensive strip if it does."""
    s = src.strip()
    if s.startswith("```"):
        # remove first fence line and trailing ```
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
    return s.strip()


def _run_go_test(test_name: str) -> tuple[int, str, str, int]:
    """Run `go test -run <test_name> -count=1 -timeout=60s ./...` in portal.
    We run ./... not just the package, so collateral damage in sibling
    packages surfaces. Returns (exit_code, stdout, stderr, duration_ms)."""
    t0 = time.time()
    try:
        res = subprocess.run(
            ["go", "test", "-run", f"^{test_name}$", "-count=1", "-timeout=60s",
             "-v", "./..."],
            cwd=str(COFFEE_PORTAL_DIR),
            capture_output=True, text=True, timeout=GO_TEST_TIMEOUT_S,
        )
        return res.returncode, res.stdout, res.stderr, int((time.time() - t0) * 1000)
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", (e.stderr or "") + "\n[TIMEOUT]", int((time.time() - t0) * 1000)


def _parse_judge(raw: str, free_mode: bool = False) -> dict:
    """Tolerant JSON extract from judge response.

    free_mode=True → expects 5-criterion rubric (adds target_choice,
    chosen_target). max total becomes 20 instead of 16.
    """
    import re
    s = raw.strip()
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.DOTALL)
        if m:
            s = m.group(1)
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return {"error": "no JSON found", "raw_head": s[:200]}
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"error": f"bad JSON: {e}", "raw_head": s[:200]}

    score_keys = ["fact_grounding", "convention_match", "coverage_depth",
                  "runs_clean"]
    if free_mode:
        score_keys.append("target_choice")

    out: dict = {}
    for k in score_keys + ["divergence"]:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            out[k] = int(v)
    out["notes"] = obj.get("notes", "")
    if free_mode:
        out["chosen_target"] = obj.get("chosen_target", "unparseable")
    out["total"] = sum(out.get(k, 0) for k in score_keys)  # max 16 or 20
    out["max_total"] = len(score_keys) * 4
    return out


# ── core ──────────────────────────────────────────────────────────────

def run_topic(approach: str, context: str, topic: dict) -> TopicResult:
    """Run one (approach, topic) pair. Caller must ensure portal is clean."""
    suffix = _suffix()
    test_name = f"TestUnitBench{suffix}"
    test_filename = f"zz_bench_{topic['id']}_{suffix.lower()}_test.go"
    test_relpath = f"{topic['package']}/{test_filename}"
    test_abspath = COFFEE_PORTAL_DIR / test_relpath

    print(f"  [tw] {approach} × {topic['id']} → {test_name}", flush=True)

    # ── 1. plan ──
    ctx = context if len(context) <= CONTEXT_CAP_CHARS else \
        context[:CONTEXT_CAP_CHARS] + "\n\n[...truncated for planner...]"
    prompt = PLANNER_PROMPT.format(
        brief=topic["brief"],
        target=topic["target"],
        package=topic["package"],
        package_name=topic["package_name"],
        module=GO_MODULE,
        unique_suffix=suffix,
        context=ctx,
    )
    src, usage, plan_lat = _call_cerebras(
        [{"role": "user", "content": prompt}],
        model=PLANNER_MODEL, max_tokens=PLANNER_MAX_TOKENS,
    )
    src = _strip_code_fence(src)

    # ── 2. write ──
    test_abspath.write_text(src, encoding="utf-8")
    print(f"        wrote {test_relpath} ({len(src)} chars)", flush=True)

    # ── 3. compile + run ──
    exit_code, stdout, stderr, dur_ms = _run_go_test(test_name)
    print(f"        go test → exit={exit_code} ({dur_ms}ms)", flush=True)

    # ── 4. judge ──
    gt = _read_ground_truth(topic["ground_truth_files"])
    free_mode = topic["id"].startswith("free_")
    prompt_tpl = FREE_JUDGE_PROMPT if free_mode else JUDGE_PROMPT
    judge_prompt = prompt_tpl.format(
        brief=topic["brief"],
        ground_truth=gt,
        test_source=src[:6000],
        exit_code=exit_code,
        duration_ms=dur_ms,
        stdout=stdout[-2000:],
        stderr=stderr[-2000:],
    )
    judge_raw, _, judge_lat = _call_deepseek(
        [{"role": "user", "content": judge_prompt}],
        model=JUDGE_MODEL, max_tokens=JUDGE_MAX_TOKENS,
    )
    scores = _parse_judge(judge_raw, free_mode=free_mode)
    max_t = scores.get("max_total", 16)
    extra = f" target={scores.get('chosen_target','?')}" if free_mode else ""
    print(f"        judge → {scores.get('total','?')}/{max_t} "
          f"div={scores.get('divergence','?')}{extra}", flush=True)

    return TopicResult(
        topic_id=topic["id"],
        target=topic["target"],
        test_name=test_name,
        test_path=test_relpath,
        plan_latency_ms=plan_lat,
        plan_tokens_in=usage.get("prompt_tokens", 0),
        plan_tokens_out=usage.get("completion_tokens", 0),
        test_source=src,
        go_exit_code=exit_code,
        go_duration_ms=dur_ms,
        go_stdout=stdout[-4000:],
        go_stderr=stderr[-4000:],
        judge_latency_ms=judge_lat,
        judge_raw=judge_raw,
        scores=scores,
    )


def run_approach(approach: str, context: str, topics: str = "both",
                 wide_seed: int | None = None) -> ApproachResult:
    """Run test-writing for one approach.

    `topics` ∈ {"fixed","wide","free","both","all"}.
      - both = fixed + wide
      - all  = fixed + wide + free
    `wide_seed` — int seed for reproducible wide-pool selection.
    Caller MUST ensure portal is clean. We rollback after EACH topic.
    """
    out = ApproachResult(approach=approach)

    # Pre-condition: portal clean
    clean, porc = _portal_clean_check()
    if not clean:
        raise RuntimeError(
            f"coffee-portal is dirty before run_approach({approach!r}):\n{porc}\n"
            "Commit or stash before running the test-writing benchmark."
        )

    do_fixed = topics in ("fixed", "both", "all")
    do_wide  = topics in ("wide", "both", "all")
    do_free  = topics in ("free", "all")

    if do_fixed:
        out.fixed = run_topic(approach, context, FIXED_TOPIC)
        _portal_rollback()

    if do_wide:
        import random
        seed = wide_seed if wide_seed is not None else hash(approach) & 0xFFFFFFFF
        rng = random.Random(seed)
        topic = rng.choice(WIDE_POOL)
        print(f"  [tw] wide pool seed={seed} → {topic['id']}", flush=True)
        out.wide = run_topic(approach, context, topic)
        _portal_rollback()

    if do_free:
        out.free = run_topic(approach, context, FREE_TOPIC)
        _portal_rollback()

    return out


# ── CLI entry-point (standalone use) ──────────────────────────────────

def _load_context(approach: str, context_path: Path | None) -> str:
    """Load saved onboarding context for an approach."""
    if context_path is not None:
        return context_path.read_text(encoding="utf-8")
    # Default: results/contexts/<approach>_latest.txt
    default = SCRIPT_DIR / "results" / "contexts" / f"{approach}_latest.txt"
    if not default.exists():
        raise FileNotFoundError(
            f"no context for {approach} at {default}. "
            "Run `make bench` first (it caches contexts) or pass --context PATH."
        )
    return default.read_text(encoding="utf-8")


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Test-writing benchmark stage")
    ap.add_argument("--approach", required=True,
                    choices=["md_files", "github_issues", "mem0", "helixir_mcp"])
    ap.add_argument("--topics", default="both",
                    choices=["fixed", "wide", "free", "both", "all"],
                    help="fixed/wide/free single mode, both=fixed+wide, all=fixed+wide+free")
    ap.add_argument("--context", type=Path, default=None,
                    help="Path to saved onboarding context. Defaults to "
                         "results/contexts/<approach>_latest.txt.")
    ap.add_argument("--seed", type=int, default=None,
                    help="Seed for wide-topic random pick (default: hash(approach))")
    args = ap.parse_args(argv)

    ctx = _load_context(args.approach, args.context)
    result = run_approach(args.approach, ctx, args.topics, args.seed)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = RESULTS_DIR / f"{ts}_{args.approach}.json"
    out_path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[tw] result → {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
