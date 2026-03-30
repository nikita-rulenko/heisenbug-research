#!/usr/bin/env python3
"""Render research comparison tables as PNG images for Heisenbug conference."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

OUT = os.path.join(os.path.dirname(__file__), "tables")
os.makedirs(OUT, exist_ok=True)

BG = "#1a1a2e"
HEADER_BG = "#16213e"
ROW_EVEN = "#0f3460"
ROW_ODD = "#1a1a2e"
ACCENT = "#e94560"
TEXT = "#eaeaea"
HEADER_TEXT = "#ffffff"
BORDER = "#533483"


def render_table(data, col_labels, row_labels, title, filename,
                 col_widths=None, highlight_col=None):
    n_rows = len(row_labels)
    n_cols = len(col_labels)

    if col_widths is None:
        col_widths = [0.18] + [0.16] * (n_cols - 1)
        total = sum(col_widths)
        col_widths = [w / total for w in col_widths]

    fig_w = max(14, n_cols * 2.2)
    fig_h = max(4, n_rows * 0.55 + 1.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    table = ax.table(
        cellText=data,
        colLabels=col_labels,
        rowLabels=row_labels,
        cellLoc="center",
        loc="center",
        colWidths=col_widths,
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.6)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor(BORDER)
        cell.set_linewidth(0.8)

        if row == 0:
            cell.set_facecolor(HEADER_BG)
            cell.set_text_props(color=HEADER_TEXT, fontweight="bold", fontsize=11)
        else:
            bg = ROW_EVEN if row % 2 == 0 else ROW_ODD
            cell.set_facecolor(bg)
            cell.set_text_props(color=TEXT, fontsize=10)

        if col == -1:
            cell.set_facecolor(HEADER_BG)
            cell.set_text_props(color=ACCENT, fontweight="bold", fontsize=10,
                                ha="left")
            cell.PAD = 0.05

        if highlight_col is not None and col == highlight_col and row > 0:
            cell.set_text_props(color=ACCENT, fontweight="bold")

    ax.set_title(title, color=HEADER_TEXT, fontsize=16, fontweight="bold",
                 pad=20, loc="left")

    path = os.path.join(OUT, filename)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=BG,
                edgecolor="none", pad_inches=0.3)
    plt.close(fig)
    print(f"  -> {path}")


# ──────────────────────────────────────────────
# TABLE 1: Main comparison of all approaches
# ──────────────────────────────────────────────
print("Table 1: Main comparison")
render_table(
    title="Сравнение подходов к управлению контекстом AI-агентов",
    filename="01_main_comparison.png",
    col_labels=["AGENTS.md", "Jira/Tickets", "Mem0", "HelixDB", "Helixir"],
    row_labels=[
        "Хранение",
        "Поиск",
        "Авто-сохранение",
        "Забывание",
        "Каузальные связи",
        "Working memory",
        "Типизация фактов",
        "Temporal filter",
        "MCP интеграция",
        "Аудируемость",
        "Production-ready",
        "Порог входа",
        "Стоимость",
        "Community",
    ],
    data=[
        [".md в repo", "DB трекера", "Vector+Graph", "Graph-Vector", "HelixDB"],
        ["Полнотекст", "Текст+фильтры", "Semantic", "Semantic+Graph", "Sem+Graph+Onto"],
        ["Нет", "Частично", "Да (LLM)", "Нет (API)", "Да (LLM)"],
        ["Нет", "Нет", "Да", "Нет", "Да (SUPERSEDE)"],
        ["Нет", "Нет", "Нет", "Возможно", "Да (native)"],
        ["Нет", "Нет", "Нет", "Нет", "Да (FastThink)"],
        ["Нет", "Тип тикета", "Нет", "Schema", "Онтология (7)"],
        ["Нет", "По дате", "Нет", "Нет", "4 режима"],
        ["Native", "API", "Да", "Нет", "Да (native)"],
        ["Git history", "Полная", "Ограничена", "API logs", "Ограничена"],
        ["Высокая", "Высокая", "Высокая", "Средняя", "Низкая"],
        ["Минимальный", "Низкий", "3 строки", "HelixQL", "MCP tools"],
        ["Бесплатно", "$0-49/agent", "Free-$499", "Free (OSS)", "Free (OSS)"],
        ["Огромная", "Огромная", "47.8K ★", "~1K ★", "74 ★"],
    ],
    highlight_col=4,
)

# ──────────────────────────────────────────────
# TABLE 2: Mem0 benchmarks
# ──────────────────────────────────────────────
print("Table 2: Mem0 benchmarks")
render_table(
    title="Бенчмарки Memory Frameworks (LOCOMO)",
    filename="02_mem0_benchmarks.png",
    col_labels=["Mem0", "Mem0ᴳ", "OpenAI", "LangMem", "Letta"],
    row_labels=[
        "J-score",
        "Latency (p95)",
        "Tokens/conv",
        "Multi-hop",
        "Temporal",
        "Stars",
        "Funding",
    ],
    data=[
        ["Best", "Best+", "Средний", "Слабый", "Средний"],
        ["1.44s", "~2s", "0.89s", "59.82s", "—"],
        ["~7K", "~14K", "—", "—", "—"],
        ["Best", "Best", "Слабый", "Средний", "Средний"],
        ["—", "J: 58.13", "—", "—", "—"],
        ["47.8K", "—", "—", "1.3K", "21.2K"],
        ["$24M", "—", "—", "OSS", "OSS"],
    ],
    highlight_col=0,
)

# ──────────────────────────────────────────────
# TABLE 3: Memory frameworks comparison
# ──────────────────────────────────────────────
print("Table 3: Memory frameworks")
render_table(
    title="Сравнение Memory Frameworks",
    filename="03_memory_frameworks.png",
    col_labels=["Mem0", "Zep", "Letta", "LangMem", "Cognee", "Helixir"],
    row_labels=[
        "Graph Memory",
        "Managed SaaS",
        "Framework-agnostic",
        "Sub-second retrieval",
        "Auto extraction",
        "Каузальные связи",
        "Working memory",
        "Онтология",
        "Stars",
        "Цена",
    ],
    data=[
        ["Да", "Да", "Ограничено", "Ограничено", "Да", "Да"],
        ["Да", "Да", "Да", "Нет", "Нет", "Нет"],
        ["Да", "Да", "Да", "Нет", "Да", "Да"],
        ["Да", "Условно", "Нет", "Нет", "Нет", "Да (Rust)"],
        ["Да", "Да", "Да", "Нет", "Нет", "Да"],
        ["Нет", "Нет", "Нет", "Нет", "Нет", "Да"],
        ["Нет", "Нет", "Нет", "Нет", "Нет", "FastThink"],
        ["Нет", "Нет", "Нет", "Нет", "Нет", "7 типов"],
        ["47.8K", "4.1K", "21.2K", "1.3K", "—", "74"],
        ["$99-499", "$25+", "$20-200", "Free", "Free", "Free"],
    ],
    highlight_col=5,
)

# ──────────────────────────────────────────────
# TABLE 4: GitHub Issues agents
# ──────────────────────────────────────────────
print("Table 4: GitHub Issues agents")
render_table(
    title="AI-агенты для GitHub Issues",
    filename="04_github_agents.png",
    col_labels=["Copilot Agent", "Kiro (AWS)", "Claude Code", "SWE-Agent", "Aider", "CodeRabbit"],
    row_labels=[
        "Тип",
        "Цена",
        "Auto-PR",
        "Code Review",
        "Issue → PR",
        "Open Source",
        "MCP support",
    ],
    data=[
        ["Coding agent", "Coding agent", "Review+fix", "Research", "Coding tool", "Review bot"],
        ["$10+/mo", "Free tier", "API costs", "Free+API", "Free+API", "Free/Pro"],
        ["Да", "Да", "Да", "Да", "Да", "Нет"],
        ["Да", "Да", "Да", "Нет", "Нет", "Да"],
        ["Да", "Да", "Частично", "Да", "Да", "Нет"],
        ["Нет", "Нет", "Нет", "Да", "Да", "Нет"],
        ["Да", "Нет", "Нет", "Нет", "Нет", "Нет"],
    ],
)

# ──────────────────────────────────────────────
# TABLE 5: Helixir vs Mem0
# ──────────────────────────────────────────────
print("Table 5: Helixir vs Mem0")
render_table(
    title="Helixir vs Mem0 — детальное сравнение",
    filename="05_helixir_vs_mem0.png",
    col_labels=["Helixir", "Mem0"],
    row_labels=[
        "Каузальные связи",
        "Working memory",
        "Онтология",
        "Backend",
        "Язык",
        "Startup",
        "Managed SaaS",
        "Stars",
        "Enterprise",
        "Maturity",
        "Benchmarks",
        "Cognitive Protocol",
    ],
    data=[
        ["IMPLIES/BECAUSE/CONTRADICTS", "Нет"],
        ["FastThink (scratchpad)", "Нет"],
        ["7 типов фактов", "Нет типизации"],
        ["HelixDB (native graph+vector)", "Qdrant/Chroma + Neo4j"],
        ["Rust", "Python"],
        ["~50ms", "~1-2s"],
        ["Нет", "Да ($99-499/mo)"],
        ["74", "47.8K"],
        ["Нет", "AWS Agent SDK"],
        ["v0.1.1", "Production-ready"],
        ["Нет", "LOCOMO (best in class)"],
        ["Авто-триггеры recall/save", "Нет"],
    ],
    highlight_col=0,
    col_widths=[0.35, 0.35],
)

# ──────────────────────────────────────────────
# TABLE 6: Decision matrix
# ──────────────────────────────────────────────
print("Table 6: Decision matrix")
render_table(
    title="Матрица принятия решений",
    filename="06_decision_matrix.png",
    col_labels=["Лучше всего для", "Не подходит для"],
    row_labels=[
        "AGENTS.md",
        "Jira / Tickets",
        "GitHub Issues",
        "Mem0",
        "HelixDB",
        "Helixir",
    ],
    data=[
        ["Быстрый старт, малые проекты", "Долгосрочная память, мультиагент"],
        ["Enterprise процессы, аудит", "Real-time AI memory, семантика"],
        ["Dev teams, бесплатный AI workflow", "Сложные enterprise процессы"],
        ["Production AI agents, SaaS", "Каузальное reasoning, бюджет"],
        ["Custom AI infra, RAG, knowledge", "Quick MVP, нет Rust-экспертизы"],
        ["Research, causal reasoning", "Production enterprise, support"],
    ],
    col_widths=[0.4, 0.4],
)

print(f"\nDone! All tables in: {OUT}/")
