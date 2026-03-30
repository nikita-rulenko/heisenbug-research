#!/usr/bin/env python3
"""Render the final demo comparison table in both dark and light themes."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

THEMES = {
    "dark": {
        "bg": "#1a1a2e", "header_bg": "#16213e", "row_even": "#0f3460",
        "row_odd": "#1a1a2e", "accent": "#e94560", "text": "#eaeaea",
        "header_text": "#ffffff", "border": "#533483",
        "rowlabel_bg": "#16213e", "rowlabel_text": "#e94560",
        "title_color": "#ffffff",
    },
    "light": {
        "bg": "#ffffff", "header_bg": "#1e3a5f", "row_even": "#f0f4f8",
        "row_odd": "#ffffff", "accent": "#c0392b", "text": "#2c3e50",
        "header_text": "#ffffff", "border": "#bdc3c7",
        "rowlabel_bg": "#e8eef4", "rowlabel_text": "#1e3a5f",
        "title_color": "#1e3a5f",
    },
}


def render(theme_name, t, data, col_labels, row_labels, title, filename,
           col_widths=None, highlight_col=None):
    n_rows, n_cols = len(row_labels), len(col_labels)
    if col_widths is None:
        col_widths = [0.18] + [0.16] * (n_cols - 1)
        s = sum(col_widths)
        col_widths = [w / s for w in col_widths]

    fig_w = max(14, n_cols * 2.4)
    fig_h = max(4, n_rows * 0.55 + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(t["bg"])
    ax.set_facecolor(t["bg"])
    ax.axis("off")

    tbl = ax.table(cellText=data, colLabels=col_labels, rowLabels=row_labels,
                   cellLoc="center", loc="center", colWidths=col_widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 1.6)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor(t["border"])
        cell.set_linewidth(0.7)
        if row == 0:
            cell.set_facecolor(t["header_bg"])
            cell.set_text_props(color=t["header_text"], fontweight="bold", fontsize=11)
        else:
            cell.set_facecolor(t["row_even"] if row % 2 == 0 else t["row_odd"])
            cell.set_text_props(color=t["text"], fontsize=10)
        if col == -1:
            cell.set_facecolor(t["rowlabel_bg"])
            cell.set_text_props(color=t["rowlabel_text"], fontweight="bold",
                                fontsize=10, ha="left")
            cell.PAD = 0.05
        if highlight_col is not None and col == highlight_col and row > 0:
            cell.set_text_props(color=t["accent"], fontweight="bold")

    ax.set_title(title, color=t["title_color"], fontsize=16,
                 fontweight="bold", pad=20, loc="left")

    out_dir = os.path.join(os.path.dirname(__file__), "tables", theme_name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=t["bg"],
                edgecolor="none", pad_inches=0.3)
    plt.close(fig)
    print(f"  -> {path}")


COL_LABELS = ["MD файлы", "Copilot Agent", "Mem0", "HelixDB", "Helixir"]

ROW_LABELS_MAIN = [
    "Тип решения",
    "Цена",
    "Хранение контекста",
    "Семантический поиск",
    "Каузальные связи",
    "Working memory",
    "Онтология фактов",
    "Temporal filtering",
    "Забывание устаревшего",
    "Аудит действий",
    "MCP интеграция",
    "Production-ready",
    "Community",
    "Для демо",
]

DATA_MAIN = [
    ["Статичный файл", "Issue tracker + agent", "Memory framework", "Graph-Vector DB", "Causal memory"],
    ["Бесплатно", "Free (50 req/mo)\n$10/mo Pro", "Free (10K mem)\n$19-249/mo", "Free (OSS)", "Free (OSS)"],
    ["Git repo (.md)", "GitHub Issues + PR", "Vector DB + Graph DB", "Native graph+vector", "HelixDB"],
    ["Нет", "Нет", "Да (embeddings)", "Да (HNSW)", "Да (SmartTraversal)"],
    ["Нет", "Нет", "Нет", "Возможно (graph)", "Да (native)"],
    ["Нет", "Нет", "Нет", "Нет", "Да (FastThink)"],
    ["Нет", "Нет", "Нет", "Schema-typed", "7 типов"],
    ["Нет", "Нет", "Нет", "Нет", "4 режима"],
    ["Нет", "Нет", "Да (auto-forget)", "Нет", "Да (SUPERSEDE)"],
    ["Git history", "Session logs + PR", "Ограниченно", "API logs", "Ограниченно"],
    ["Native (файлы)", "GitHub MCP", "Mem0 MCP", "Нет", "Native MCP"],
    ["Стандарт", "GA (GitHub)", "Production", "Early (YC)", "v0.1.1 (research)"],
    ["Огромная", "15M devs", "47.8K stars", "YC/Nvidia/Vercel", "74 stars"],
    ["Показать базу", "Показать workflow", "Показать память", "Показать storage", "Показать reasoning"],
]

ROW_LABELS_MEM0 = [
    "Setup time",
    "Инфраструктура",
    "Цена",
    "Vector DB",
    "LLM выбор",
    "Graph Memory",
    "Webhooks",
    "Memory export",
    "Auto-scaling",
    "HA",
    "Compliance",
    "Data residency",
]

DATA_MEM0 = [
    ["5 минут", "15 мин — часы"],
    ["Managed (Mem0)", "Своя (VM+DB)"],
    ["Free 10K / $19 / $249", "Бесплатно + infra"],
    ["Managed", "24+ (Qdrant, Chroma...)"],
    ["Managed", "16+ (OpenAI, Ollama...)"],
    ["Managed", "Self-configured"],
    ["Да", "Нет"],
    ["Да", "Нет"],
    ["Да", "Manual"],
    ["Built-in", "DIY"],
    ["SOC 2, GDPR", "Своя ответственность"],
    ["US (expandable)", "Любая юрисдикция"],
]

for theme_name, t in THEMES.items():
    print(f"\n=== {theme_name.upper()} ===")

    print("Table: Main demo comparison")
    render(theme_name, t,
           title="Heisenbug 2026 — 5 подходов к контексту AI-агентов",
           filename="07_demo_comparison.png",
           data=DATA_MAIN, col_labels=COL_LABELS, row_labels=ROW_LABELS_MAIN,
           highlight_col=4)

    print("Table: Mem0 Platform vs OSS")
    render(theme_name, t,
           title="Mem0: Platform (Cloud) vs Open Source (Self-hosted)",
           filename="08_mem0_platform_vs_oss.png",
           data=DATA_MEM0,
           col_labels=["Platform (Cloud)", "Open Source (Self-hosted)"],
           row_labels=ROW_LABELS_MEM0,
           col_widths=[0.35, 0.35])

print("\nDone!")
