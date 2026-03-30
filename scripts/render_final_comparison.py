#!/usr/bin/env python3
"""Render the final 4-solution comparison table — dark & light themes."""

import os
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

THEMES = {
    "dark": {
        "bg": "#1a1a2e", "header_bg": "#16213e", "row_even": "#0f3460",
        "row_odd": "#1a1a2e", "text": "#eaeaea", "star": "#ffd700",
        "header_text": "#ffffff", "border": "#533483",
        "rowlabel_bg": "#16213e", "rowlabel_text": "#b8c5d6",
        "title_color": "#ffffff", "group_bg": "#0a0f1f", "group_text": "#e94560",
    },
    "light": {
        "bg": "#ffffff", "header_bg": "#1e3a5f", "row_even": "#f0f4f8",
        "row_odd": "#ffffff", "text": "#2c3e50", "star": "#d4a017",
        "header_text": "#ffffff", "border": "#bdc3c7",
        "rowlabel_bg": "#e8eef4", "rowlabel_text": "#34495e",
        "title_color": "#1e3a5f", "group_bg": "#d5e1ed", "group_text": "#c0392b",
    },
}

COLS = ["MD файлы", "GitHub Issues\nMCP", "Mem0", "Helixir"]

STAR = "\u2605"

GROUPS = [
    ("АРХИТЕКТУРА", [
        ("Тип решения",
         ["Статичные файлы\nв репозитории",
          "Issue tracker\n+ MCP tool",
          f"Memory framework\n(vector + graph) {STAR}",
          f"Causal memory\nframework {STAR}"]),
        ("Хранение контекста",
         ["Git (.md файлы)",
          "GitHub API\n(issues, comments)",
          f"Vector DB + Graph DB\n(managed/self) {STAR}",
          f"HelixDB\n(graph + vector) {STAR}"]),
        ("LLM в pipeline",
         [f"Нет {STAR}",
          f"Нет {STAR}",
          "Да (extraction\n+ dedup + embed)",
          "Да (extraction\n+ dedup + embed)"]),
        ("Стоимость LLM\nна операцию",
         [f"$0 {STAR}",
          f"$0 {STAR}",
          "~1-3K tokens\nна add()",
          "~1K tokens\nна add_memory()"]),
    ]),
    ("ВОЗМОЖНОСТИ ПАМЯТИ", [
        ("Семантический\nпоиск",
         ["Нет",
          "Нет",
          f"Да (embeddings) {STAR}",
          f"Да\n(SmartTraversal) {STAR}"]),
        ("Граф связей",
         ["Нет",
          "Нет (плоские\nissues)",
          f"Да (entity\ngraph) {STAR}",
          f"Да (native\ngraph) {STAR}"]),
        ("Каузальные\nцепочки",
         ["Нет",
          "Нет",
          "Нет",
          f"Да (IMPLIES,\nBECAUSE...) {STAR}"]),
        ("Авто-извлечение\nфактов",
         ["Нет (ручное\nнаписание)",
          "Нет (ручное\nсоздание issue)",
          f"Да (LLM\nextraction) {STAR}",
          f"Да (LLM\nextraction) {STAR}"]),
        ("Дедупликация /\nразрешение конфликтов",
         ["Нет (Git merge)",
          "Нет",
          f"Да (LLM\ndedup) {STAR}",
          f"Да (SUPERSEDE,\nCONTRADICTS) {STAR}"]),
        ("Working memory\n(scratchpad)",
         ["Нет",
          "Нет",
          "Нет",
          f"Да\n(FastThink) {STAR}"]),
        ("Онтология\nфактов",
         ["Нет (свободный\nтекст)",
          "Labels\n(ограниченно)",
          "Нет (flat\nmemories)",
          f"7 типов\n(skill, goal...) {STAR}"]),
        ("Temporal\nfiltering",
         ["Нет (всё\nили ничего)",
          "Да (date\nfilters)",
          "Ограниченно\n(metadata)",
          f"4 режима\n(4h/30d/90d/all) {STAR}"]),
        ("Cross-session\npersistence",
         ["Да (Git)",
          f"Да (GitHub\nAPI) {STAR}",
          f"Да (vector +\ngraph DB) {STAR}",
          f"Да\n(HelixDB) {STAR}"]),
        ("Multi-user\nisolation",
         ["Нет (общий\nдля всех)",
          f"Да (assignee,\nperms) {STAR}",
          f"Да (user_id,\nagent_id) {STAR}",
          "Ограниченно\n(v0.1)"]),
    ]),
    ("ИНТЕГРАЦИЯ", [
        ("MCP поддержка\n(Cursor)",
         [f"Native\n(файлы в repo) {STAR}",
          f"GitHub MCP\nServer (GA) {STAR}",
          f"Mem0 MCP\nServer {STAR}",
          f"Native MCP\n{STAR}"]),
        ("Setup time",
         [f"0 минут\n(создать файл) {STAR}",
          "5 мин\n(OAuth в Cursor)",
          "5 мин (cloud)\n30+ мин (self)",
          "15-30 мин\n(HelixDB + config)"]),
        ("SDK / языки",
         ["Любой (текст)",
          "REST API\n(любой язык)",
          f"Python, JS\n{STAR}",
          "Rust (MCP)"]),
        ("Vendor lock-in",
         [f"Нет {STAR}",
          "GitHub",
          "Mem0 (cloud)\nНет (OSS)",
          "Нет (OSS)\nLLM нужен"]),
    ]),
    ("ОПЕРАЦИОННЫЕ", [
        ("Цена",
         [f"$0 {STAR}",
          f"$0 (Free tier)\n$10/mo Pro",
          "$0 (OSS)\n$19-249/mo cloud",
          "$0 (OSS)\n+ LLM tokens"]),
        ("Latency\n(чтение)",
         [f"<1ms\n(локальный файл) {STAR}",
          "100-300ms\n(GitHub API)",
          "50-100ms (cloud)\n<10ms (local)",
          f"<5ms\n(compiled queries) {STAR}"]),
        ("Privacy /\ndata sovereignty",
         [f"Полная\n(всё в repo) {STAR}",
          "GitHub servers\n(US/EU)",
          "Cloud: Mem0 US\nOSS: полная",
          "Self-hosted +\nLLM API (или Ollama)"]),
        ("Production\nreadiness",
         [f"Стандарт {STAR}",
          f"GA (GitHub) {STAR}",
          f"Production\n(SOC2, GDPR) {STAR}",
          "v0.1.1\n(research)"]),
        ("Community /\nэкосистема",
         [f"Огромная {STAR}",
          f"15M devs {STAR}",
          f"47.8K stars\n$24M raised {STAR}",
          "74 stars\n1 maintainer"]),
    ]),
]


def render(theme_name, t):
    all_rows = []
    group_indices = []
    for group_name, rows in GROUPS:
        group_indices.append(len(all_rows))
        all_rows.append(("__GROUP__", group_name))
        for label, cells in rows:
            all_rows.append((label, cells))

    n_rows = len(all_rows)
    n_cols = len(COLS)

    fig_w = 18
    fig_h = n_rows * 0.72 + 2.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(t["bg"])
    ax.set_facecolor(t["bg"])
    ax.axis("off")

    cell_data = []
    row_labels = []
    group_row_set = set()

    for i, (label, content) in enumerate(all_rows):
        if label == "__GROUP__":
            cell_data.append([""] * n_cols)
            row_labels.append(content)
            group_row_set.add(i)
        else:
            cell_data.append(content)
            row_labels.append(label)

    col_widths = [0.22, 0.22, 0.22, 0.22]
    s = sum(col_widths)
    col_widths = [w / s for w in col_widths]

    tbl = ax.table(
        cellText=cell_data,
        colLabels=COLS,
        rowLabels=row_labels,
        cellLoc="center",
        loc="center",
        colWidths=col_widths,
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 2.2)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor(t["border"])
        cell.set_linewidth(0.5)

        actual_row = row - 1

        if row == 0:
            cell.set_facecolor(t["header_bg"])
            cell.set_text_props(
                color=t["header_text"], fontweight="bold", fontsize=12
            )
            cell.set_height(cell.get_height() * 1.1)
            continue

        if actual_row in group_row_set:
            cell.set_facecolor(t["group_bg"])
            if col == -1:
                cell.set_text_props(
                    color=t["group_text"], fontweight="bold", fontsize=11
                )
            else:
                cell.set_text_props(color=t["group_bg"], fontsize=1)
            cell.set_edgecolor(t["group_bg"])
            continue

        if col == -1:
            cell.set_facecolor(t["rowlabel_bg"])
            cell.set_text_props(
                color=t["rowlabel_text"], fontweight="bold",
                fontsize=9.5, ha="left"
            )
            cell.PAD = 0.04
        else:
            bg = t["row_even"] if actual_row % 2 == 0 else t["row_odd"]
            cell.set_facecolor(bg)
            txt = cell.get_text().get_text()
            if STAR in txt:
                cell.set_text_props(color=t["star"], fontweight="bold", fontsize=10)
            else:
                cell.set_text_props(color=t["text"], fontsize=10)

    ax.set_title(
        "Heisenbug 2026 — Сравнение 4 подходов к контексту AI-агентов",
        color=t["title_color"], fontsize=17, fontweight="bold", pad=24, loc="left",
    )

    legend_text = f"{STAR} = преимущество над остальными по данному критерию"
    ax.annotate(
        legend_text, xy=(0.0, -0.01), xycoords="axes fraction",
        fontsize=10, color=t["text"], style="italic",
    )

    out_dir = os.path.join(os.path.dirname(__file__), "tables", theme_name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "09_final_4_solutions.png")
    fig.savefig(
        path, dpi=200, bbox_inches="tight", facecolor=t["bg"],
        edgecolor="none", pad_inches=0.4,
    )
    plt.close(fig)
    print(f"  -> {path}")


for name, t in THEMES.items():
    print(f"\n=== {name.upper()} ===")
    render(name, t)

print("\nDone!")
