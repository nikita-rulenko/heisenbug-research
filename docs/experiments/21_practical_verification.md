# Практическая верификация: 4 подхода к онбордингу (2026-04-14)

## TL;DR
Протестировали 4 онбординговых промта в Cursor Composer на масштабированном проекте
(336 функций, ~637 прогонов). Все подходы дали корректные результаты при актуальных данных.
Ключевая находка: **ложный факт в Mem0** невозможно исправить из-за дедупликации,
в Helixir — исправлен через `update_memory`.

## Методология

- **IDE**: Cursor (Composer mode)
- **Промты**: [4 стандартизированных XML-промта](https://github.com/nikita-rulenko/heisenbug-coffee-portal/tree/master/prompts) (роль QA-инженера, верификация через `go test`)
- **Проект**: [Bean & Brew](https://github.com/nikita-rulenko/heisenbug-coffee-portal), 336 функций, ~637 прогонов в `go test -v`
- **Ограничение MCP**: каждый промт явно запрещает использование других MCP-серверов

## Результаты по подходам

### 1. MD-файлы

**Промт:** [onboarding_md_files.md](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/prompts/onboarding_md_files.md)
**Контекстные файлы:** [AGENTS.md](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/AGENTS.md), [.cursor/rules/](https://github.com/nikita-rulenko/heisenbug-coffee-portal/tree/master/.cursor/rules), [docs/](https://github.com/nikita-rulenko/heisenbug-coffee-portal/tree/master/docs)

**Статус:** Корректный онбординг

- Агент прочитал AGENTS.md, 5 cursor rules, 4 docs
- Все числа совпали: 336 функций, ~637 прогонов
- Coverage верифицировано через `go test -cover`
- Инфра-проблем: 0

**Наблюдение:** Агент отметил, что формулировка «~637 sub-tests через t.Run()» вводит в
заблуждение — это не 637 литеральных `t.Run()` в коде, а 637 строк `=== RUN` в verbose output.
Исправлено во всех файлах на «~637 прогонов в `go test -v`».

### 2. GitHub Issues

**Промт:** [onboarding_github_issues.md](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/prompts/onboarding_github_issues.md)
**Issues:** [heisenbug-coffee-portal/issues](https://github.com/nikita-rulenko/heisenbug-coffee-portal/issues)
**Правила агента:** [.cursor/rules/github.mdc](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/.cursor/rules/github.mdc)

**Статус:** Корректный онбординг + двусторонняя связь

- Агент загрузил 14 Issues через GitHub MCP
- Корректно идентифицировал living docs (#8, #9) и не пытался их закрыть
- Добавил комментарий в #14 (двусторонняя связь)
- Распознал чекбоксы и состояние задач

**Инфра-проблема:** GraphQL таймаут при первом вызове `gh issue view` — повторный запрос
прошёл успешно.

**Побочный эффект:** Агент попытался вызвать Helixir MCP, хотя промт этого не требовал.
Исправлено добавлением явного ограничения «используй ТОЛЬКО этот подход» во все промты.

### 3. Mem0

**Промт:** [onboarding_mem0.md](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/prompts/onboarding_mem0.md)
**Правила агента:** [.cursor/rules/mem0.mdc](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/.cursor/rules/mem0.mdc)

**Статус:** Онбординг с ложным фактом

- Агент выполнил `search_memory` по 5 запросам
- Нашёл 15 записей (часть актуальных, часть устаревших)
- **Обнаружил ложный факт** `7fb83211`: «TestIntegrationProductSearch is potentially flaky
  because it shares the in-memory database with other tests»
- В реальности каждый тест изолирован через `setupTestDB()` → отдельная `:memory:`

**Попытка исправления (неудачная):**
1. `add_memory` с исправленным текстом → «Added 0 memories» (дедупликация)
2. `update_memory` отсутствует в MCP-конфигурации Mem0
3. Единственный путь: `delete_memory` + `add_memory` — но даже это не гарантирует,
   что Mem0 примет новый факт

**Вывод:** Ложный факт с неплохим similarity score будет возвращаться при каждом поиске,
вводя агента в заблуждение. Это идеальная иллюстрация проблемы staleness в семантической памяти.

### 4. Helixir

**Промт:** [onboarding_helixir.md](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/prompts/onboarding_helixir.md)
**Правила агента:** [.cursor/rules/helixir.mdc](https://github.com/nikita-rulenko/heisenbug-coffee-portal/blob/master/.cursor/rules/helixir.mdc)

**Статус:** Онбординг + коррекция данных

- Агент выполнил 4 типа поиска: search_memory, search_reasoning_chain,
  search_by_concept, search_incomplete_thoughts
- Нашёл устаревшие данные (62 теста вместо 336)
- Нашёл reasoning chains от прошлых сессий
- **Исправил ложный факт** о shared DB через `update_memory`
- Создал новую reasoning chain с актуальными метриками

**Инфра-проблема:** FastThink сессия таймаутнулась между сообщениями. Пришлось пересоздать
сессию (`onboarding-update-v2`). Рекомендация: выполнять весь цикл FastThink в одном сообщении.

## Сравнительная таблица

| Критерий | MD | Issues | Mem0 | Helixir |
|----------|-----|--------|------|---------|
| Корректность данных | Актуальны | Актуальны | ⚠️ Ложный факт | Обновлены |
| Инфра-проблемы | 0 | GraphQL timeout | 0 | FastThink timeout |
| Двусторонняя связь | Нет | Комментарий в #14 | Нет | Reasoning chain |
| Коррекция ошибок | Перезапись файла | Edit issue | Невозможна (dedup) | update_memory |
| Видимость команде | git diff | Issue timeline | Нет | Нет |
| MCP-изоляция | N/A (нет MCP) | Нарушена¹ | Соблюдена | Соблюдена |

¹ Исправлено добавлением явного ограничения в промт.

## Ключевые выводы

1. **Все подходы работают при актуальных данных.** Разница проявляется при staleness —
   устаревшие данные в Mem0 ведут к ложным выводам, которые невозможно исправить.

2. **Helixir — единственный подход с коррекцией ошибок в семантической памяти.**
   `update_memory` позволяет точечно исправить факт без пересоздания.

3. **Issues — единственный подход с видимостью для команды.**
   Комментарий агента в Issue виден всем разработчикам, не только следующему AI-агенту.

4. **MD — самый надёжный при актуальных данных.**
   Нулевая инфраструктура, нулевые инфра-проблемы, но полностью ручное обслуживание.

5. **MCP-изоляция критична.** Без явного ограничения агент пытается использовать все
   доступные MCP-серверы, что ломает чистоту эксперимента.

## Рекомендации для промтов онбординга

- Использовать XML-теги для структуры (role, task, context_source, verification)
- Явно ограничивать доступные MCP-серверы
- Включать пример ожидаемого output
- Требовать верификацию через `go test` (фактическая проверка vs данные из памяти)
- Добавлять шаг обратной связи (комментарий в Issue, update_memory, reasoning chain)
