# Документация исследования

## Навигация

### Обзор литературы и анализ (`background/`)

| # | Документ | Описание |
|---|----------|----------|
| 01 | [Spec-Driven Development](background/01_spec_driven_development.md) | Подход к управлению контекстом через спецификации |
| 02 | [Jira Ticket Context](background/02_jira_ticket_context.md) | Анализ тикетных систем для хранения контекста |
| 02b | [GitHub Issues + Agents](background/02b_github_issues_agents.md) | GitHub Issues как инструмент для AI-агентов |
| 03 | [Mem0 Framework](background/03_mem0_framework.md) | Обзор Mem0: архитектура, возможности, ограничения |
| 04 | [HelixDB](background/04_helixdb.md) | HelixDB: графовая база данных |
| 05 | [Helixir Memory Framework](background/05_helixir_memory_framework.md) | Helixir: графовая память с FastThink pipeline |
| 06 | [Сравнительная таблица](background/06_comparison_table.md) | Сводное сравнение всех подходов |
| 07 | [Demo Comparison](background/07_demo_comparison.md) | Практическое сравнение для демонстрации |
| 08 | [Критерии оценки](background/08_criteria_explained.md) | Объяснение критериев бенчмарка |
| 09 | [Testing Context](background/09_testing_context.md) | Контекст тестирования: покрытие и стратегия |
| 10 | [Mem0 vs Helixir](background/10_evolution_and_mem0_vs_helixir.md) | Эволюция и сравнение Mem0 и Helixir |
| 11 | [Talk Framing](background/11_talk_framing.md) | Структура и фрейминг доклада |

### Эксперименты (`experiments/`)

| # | Документ | Подход | Ключевые находки |
|---|----------|--------|-----------------|
| 13 | [MD-файлы](experiments/13_experiment_md_files.md) | `.cursor/rules` + `AGENTS.md` | Простейший setup, деградация на связности |
| 14 | [GitHub Issues](experiments/14_experiment_github_issues.md) | GitHub MCP + Issues | Структурированно, но без семантики |
| 15 | [Mem0](experiments/15_experiment_mem0.md) | Self-hosted + pgvector | 6 патчей, vendor lock, но семантика работает |
| 17 | [Graphiti](experiments/17_experiment_graphiti.md) | FalkorDB + getzep SDK | Vendor lock на OpenAI Responses API |
| 18 | [Helixir Roadmap](experiments/18_helixir_issues_and_roadmap.md) | HelixDB + FastThink | Graph reasoning работает, extraction нестабилен |

### Бенчмарк (`benchmark/`)

| # | Документ | Описание |
|---|----------|----------|
| 12 | [Дизайн бенчмарка](benchmark/12_benchmark_design.md) | Сценарии, метрики, протокол оценки |
| 16 | [Результаты](benchmark/16_benchmark_results.md) | Полные результаты по всем частям (A+B+C) |
