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
| 18 | [Helixir Roadmap](experiments/18_helixir_issues_and_roadmap.md) | HelixDB + FastThink | Graph reasoning работает, extraction нестабилен |

### Методология бенчмарка (`methodology/`)

| # | Документ | Описание |
|---|----------|----------|
| 01 | [Дизайн бенчмарка](methodology/01_design.md) | Сценарии, метрики, протокол оценки, эволюция v0→v2 |
| 02 | [Как устроена оценка](methodology/02_how_it_works.md) | Все 22 вопроса + полный eval-промт verbatim |
| 03 | [Phase 4 plan](methodology/03_phase4_plan.md) | Честность бенчмарка: что видим как слабое в v2/v3, как закрываем в v4 |
| 04 | [v4 task-spec design](methodology/04_v4_taskspec_design.md) | Почему v4 — task-spec + critic, а не ещё одни вопросы |

### Результаты бенчмарков (`results/`)

| Документ | Описание |
|----------|----------|
| [v2 results](results/v2_results.md) | 175-тестовый прогон: 4 подхода × Part A+B+C, headline |
| [v3 results](results/v3_results.md) | 637-тестовый прогон: что изменилось, stale memory эффект |
| [Context recovery](results/context_recovery.md) | Онбординг-бенчмарк: accuracy + стоимость токенов по подходам |
| [v4 task-spec results](results/v4_taskspec_results.md) | Planner+critic прогон (после запуска) |
