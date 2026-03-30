#!/usr/bin/env python3
"""Compact slide-ready comparison table with icons."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

YES = "\u2713"     # ✓
NO = "\u2717"      # ✗
STAR = "\u2605"    # ★

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

COLS = ["MD файлы", "GitHub Issues MCP", "Mem0", "Helixir"]

# (row_label, [md, github, mem0, helixir])
# Values: "y" = yes, "n" = no, "s" = star (best), "p" = partial
ROWS = [
    ("Бесплатность",               ["s", "p", "p", "p"]),
    ("Без LLM-вызовов в pipeline", ["s", "s", "n", "n"]),
    ("Семантический поиск",        ["n", "n", "s", "y"]),
    ("Граф связей",                ["n", "n", "y", "s"]),
    ("Каузальные цепочки",         ["n", "n", "n", "s"]),
    ("Авто-извлечение фактов",     ["n", "n", "s", "y"]),
    ("Working memory",             ["n", "n", "n", "s"]),
    ("Онтология фактов",           ["n", "n", "n", "s"]),
    ("Temporal filtering",         ["n", "p", "p", "s"]),
    ("Multi-user isolation",       ["n", "s", "s", "n"]),
    ("MCP (Cursor)",               ["y", "y", "y", "y"]),
    ("Production-ready",           ["s", "s", "s", "n"]),
    ("Privacy / data sovereignty",  ["s", "n", "p", "p"]),
    ("Community / ecosystem",       ["y", "s", "s", "n"]),
]


def icon(val):
    if val == "s":
        return STAR
    elif val == "y":
        return YES
    elif val == "p":
        return "~"
    else:
        return NO


def color_for(val, t):
    if val == "s":
        return t["star"]
    elif val == "y":
        return t["yes"]
    elif val == "p":
        return t["text"]
    else:
        return t["no"]


def render(theme_name, t):
    cell_data = [[icon(v) for v in row[1]] for row in ROWS]
    row_labels = [r[0] for r in ROWS]
    n_rows = len(ROWS)
    n_cols = len(COLS)

    fig_w = 13
    fig_h = n_rows * 0.62 + 2.8
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
            cell.set_text_props(
                color=t["header_text"], fontweight="bold", fontsize=13,
            )
            continue

        if col == -1:
            cell.set_facecolor(t["rowlabel_bg"])
            cell.set_text_props(
                color=t["rowlabel_text"], fontweight="bold",
                fontsize=11, ha="left",
            )
            cell.PAD = 0.05
        else:
            actual_row = row - 1
            bg = t["row_even"] if actual_row % 2 == 0 else t["row_odd"]
            cell.set_facecolor(bg)
            val = ROWS[actual_row][1][col]
            c = color_for(val, t)
            cell.set_text_props(color=c, fontweight="bold", fontsize=16)

    ax.set_title(
        "Heisenbug 2026 — Контекст AI-агентов: 4 подхода",
        color=t["title_color"], fontsize=16, fontweight="bold", pad=20, loc="left",
    )

    legend = f"{STAR} лучший    {YES} да    ~ частично    {NO} нет"
    ax.annotate(
        legend, xy=(0.0, -0.015), xycoords="axes fraction",
        fontsize=11, color=t["text"],
    )

    out_dir = os.path.join(os.path.dirname(__file__), "tables", theme_name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "10_slide_comparison.png")
    fig.savefig(
        path, dpi=200, bbox_inches="tight", facecolor=t["bg"],
        edgecolor="none", pad_inches=0.35,
    )
    plt.close(fig)
    print(f"  -> {path}")


for name, t in THEMES.items():
    print(f"\n=== {name.upper()} ===")
    render(name, t)

print("\nDone!")
