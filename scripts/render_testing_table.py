#!/usr/bin/env python3
"""Render testing-focused comparison table for Heisenbug 2026."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

YES = "\u2713"
NO = "\u2717"
STAR = "\u2605"

THEMES = {
    "dark": {
        "bg": "#1a1a2e", "header_bg": "#16213e", "row_even": "#0f3460",
        "row_odd": "#1a1a2e", "text": "#eaeaea", "yes": "#2ecc71",
        "no": "#666680", "star": "#ffd700", "header_text": "#ffffff",
        "border": "#533483", "rowlabel_bg": "#16213e", "rowlabel_text": "#b8c5d6",
        "title_color": "#ffffff",
    },
    "light": {
        "bg": "#ffffff", "header_bg": "#1e3a5f", "row_even": "#f0f4f8",
        "row_odd": "#ffffff", "text": "#2c3e50", "yes": "#27ae60",
        "no": "#bdc3c7", "star": "#d4a017", "header_text": "#ffffff",
        "border": "#bdc3c7", "rowlabel_bg": "#e8eef4", "rowlabel_text": "#34495e",
        "title_color": "#1e3a5f",
    },
}

COLS = ["MD файлы", "GitHub Issues\nMCP", "Mem0", "Helixir"]

ROWS = [
    ("Знание тест-конвенций\n(framework, dirs, commands)",  ["s", "y", "y", "y"]),
    ("Помнит прошлые\nтест-сессии",                         ["n", "p", "s", "s"]),
    ("Semantic search\nпо тест-паттернам",                   ["n", "n", "s", "y"]),
    ("Root cause memory\n(почему тест падал)",                ["n", "p", "p", "s"]),
    ("Flaky test debugging\n(history + fix)",                 ["n", "p", "y", "s"]),
    ("Audit trail\nCI failures",                             ["n", "s", "n", "n"]),
    ("Эволюция тест-стратегии\n(was→now)",                   ["p", "n", "n", "s"]),
    ("Масштаб: 2000+ тестов\n(context retrieval)",           ["n", "n", "s", "s"]),
    ("FastThink для\nсложного debugging",                    ["n", "n", "n", "s"]),
    ("Collaboration\nQA + AI в одном месте",                 ["p", "s", "n", "p"]),
    ("Self-healing tests\n(UI/API change → autofix)",        ["p", "y", "y", "y"]),
    ("Zero LLM cost",                                        ["s", "s", "n", "n"]),
    ("Production-ready",                                     ["s", "s", "s", "n"]),
]


def icon(val):
    return {
        "s": STAR, "y": YES, "p": "~", "n": NO,
    }[val]


def color_for(val, t):
    return {
        "s": t["star"], "y": t["yes"], "p": t["text"], "n": t["no"],
    }[val]


def render(theme_name, t):
    cell_data = [[icon(v) for v in r[1]] for r in ROWS]
    row_labels = [r[0] for r in ROWS]
    n_cols = len(COLS)

    fig_w = 13
    fig_h = len(ROWS) * 0.62 + 2.8
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(t["bg"])
    ax.set_facecolor(t["bg"])
    ax.axis("off")

    col_widths = [0.25] * n_cols
    tbl = ax.table(
        cellText=cell_data, colLabels=COLS, rowLabels=row_labels,
        cellLoc="center", loc="center", colWidths=col_widths,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(13)
    tbl.scale(1, 2.4)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor(t["border"])
        cell.set_linewidth(0.5)
        if row == 0:
            cell.set_facecolor(t["header_bg"])
            cell.set_text_props(color=t["header_text"], fontweight="bold", fontsize=13)
            continue
        if col == -1:
            cell.set_facecolor(t["rowlabel_bg"])
            cell.set_text_props(color=t["rowlabel_text"], fontweight="bold",
                                fontsize=10.5, ha="left")
            cell.PAD = 0.05
        else:
            bg = t["row_even"] if (row - 1) % 2 == 0 else t["row_odd"]
            cell.set_facecolor(bg)
            val = ROWS[row - 1][1][col]
            cell.set_text_props(color=color_for(val, t), fontweight="bold", fontsize=16)

    ax.set_title(
        "Heisenbug 2026 — Контекст AI-агентов для автотестов",
        color=t["title_color"], fontsize=16, fontweight="bold", pad=20, loc="left",
    )
    ax.annotate(
        f"{STAR} лучший    {YES} да    ~ частично    {NO} нет",
        xy=(0.0, -0.015), xycoords="axes fraction", fontsize=11, color=t["text"],
    )

    out = os.path.join(os.path.dirname(__file__), "tables", theme_name)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "11_testing_comparison.png")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=t["bg"],
                edgecolor="none", pad_inches=0.35)
    plt.close(fig)
    print(f"  -> {path}")


for name, t in THEMES.items():
    print(f"\n=== {name.upper()} ===")
    render(name, t)

print("\nDone!")
