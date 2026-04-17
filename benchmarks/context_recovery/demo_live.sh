#!/bin/bash
# Heisenbug 2026 — Live Demo Script
# Демонстрация 5 подходов к управлению контекстом AI-агентов
#
# Требования:
#   - Docker (Mem0, HelixDB)
#   - Ollama (nomic-embed-text)
#   - gh CLI (GitHub Issues)
#   - CEREBRAS_API_KEY

set -e

PORTAL_DIR="${PORTAL_DIR:-$HOME/Downloads/heisenbug-coffee-portal}"
RESEARCH_DIR="${RESEARCH_DIR:-$HOME/Downloads/heisenbug-research}"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

pause() {
    echo ""
    echo -e "${YELLOW}[Enter для продолжения]${NC}"
    read -r
}

# ─── 0. Проверка инфраструктуры ───
echo -e "${BLUE}═══ Проверка инфраструктуры ═══${NC}"
echo -n "Ollama: "; ollama list 2>/dev/null | grep nomic-embed && echo "  ✓" || echo "  ✗ (нужен: ollama pull nomic-embed-text)"
echo -n "Mem0:   "; curl -s http://localhost:8888/search -X POST -H "Content-Type: application/json" -d '{"query":"test","user_id":"heisenbug"}' | python3 -c "import sys,json; r=json.load(sys.stdin); print(f'  ✓ ({len(r.get(\"results\",[]))} memories)')" 2>/dev/null || echo "  ✗ (docker compose up -d в infra/mem0/)"
echo -n "HelixDB:"; curl -s http://localhost:6970/ >/dev/null 2>&1 && echo " ✓" || echo " ✗ (helix deploy local bench в infra/helixir-local/)"
echo -n "Go тесты:"; cd "$PORTAL_DIR" && go test ./... -count=1 2>&1 | tail -1 || echo " ✗"
pause

# ─── 1. MD-файлы ───
echo -e "${GREEN}═══ Подход 1: MD-файлы (.cursor/rules + AGENTS.md) ═══${NC}"
echo "Контекст хранится в plain text файлах:"
echo ""
echo "=== AGENTS.md (первые 20 строк) ==="
head -20 "$PORTAL_DIR/AGENTS.md" 2>/dev/null || echo "(файл не найден)"
echo ""
echo "=== .cursor/rules/testing.mdc ==="
head -20 "$PORTAL_DIR/.cursor/rules/testing.mdc" 2>/dev/null || echo "(файл не найден)"
echo ""
echo -e "📊 Benchmark v2: ${GREEN}123/192 (64.1%)${NC} | σ=2.08 — самый стабильный"
pause

# ─── 2. GitHub Issues ───
echo -e "${GREEN}═══ Подход 2: GitHub Issues MCP ═══${NC}"
echo "Контекст структурирован в issues с labels:"
echo ""
gh issue list -R nikita-rulenko/heisenbug-coffee-portal --label "context:coverage" --limit 5 2>/dev/null || echo "(gh CLI не настроен)"
echo ""
echo "Пример issue body:"
gh issue view 1 -R nikita-rulenko/heisenbug-coffee-portal --json title,labels,body 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Title: {d[\"title\"]}')
print(f'Labels: {[l[\"name\"] for l in d[\"labels\"]]}')
print(f'Body (первые 300 символов): {d[\"body\"][:300]}...')
" 2>/dev/null || echo "(gh CLI не настроен)"
echo ""
echo -e "📊 Benchmark v2: ${GREEN}122/192 (63.5%)${NC} | σ=12.66 — высокая дисперсия"
pause

# ─── 3. Mem0 (self-hosted) ───
echo -e "${GREEN}═══ Подход 3: Mem0 — семантическая память ═══${NC}"
echo "Семантический поиск по pgvector:"
echo ""
echo "Запрос: 'какие тесты покрывают Order'"
echo ""
curl -s -X POST http://localhost:8888/search \
  -H "Content-Type: application/json" \
  -d '{"query": "какие тесты покрывают Order", "user_id": "heisenbug"}' | \
  python3 -c "
import sys,json
r=json.load(sys.stdin)
for m in r.get('results',[]):
    print(f'  score={m[\"score\"]:.3f} | {m[\"memory\"][:100]}')
" 2>/dev/null || echo "(Mem0 не отвечает)"
echo ""
echo "Запрос: 'state machine'"
curl -s -X POST http://localhost:8888/search \
  -H "Content-Type: application/json" \
  -d '{"query": "state machine", "user_id": "heisenbug"}' | \
  python3 -c "
import sys,json
r=json.load(sys.stdin)
for m in r.get('results',[]):
    print(f'  score={m[\"score\"]:.3f} | {m[\"memory\"][:100]}')
" 2>/dev/null || echo "(Mem0 не отвечает)"
echo ""
echo -e "📊 Benchmark v2: ${GREEN}125/192 (65.1%) — 1-е место${NC} | σ=10.97"
pause

# ─── 4. Helixir (graph + FastThink) ───
echo -e "${GREEN}═══ Подход 4: Helixir — графовая память с reasoning ═══${NC}"
echo "HelixDB + graph relations (IMPLIES/BECAUSE/CONTRADICTS):"
echo ""
echo "Контейнер: $(docker ps --filter name=helix --format '{{.Names}} {{.Status}}')"
echo ""
echo -e "📊 Benchmark v2: ${GREEN}121/192 (63.0%)${NC} | σ=16.70"
echo "   Преимущества проявляются в Part B (связность) и Part C (reasoning)"
pause

# ─── Итоговая таблица ───
echo -e "${BLUE}═══ Итоговая таблица v2 ═══${NC}"
echo ""
printf "%-20s %8s %15s %6s\n" "Подход" "Median" "Mean ± σ" "%"
printf "%-20s %8s %15s %6s\n" "──────────────────" "────────" "───────────────" "──────"
printf "%-20s %8s %15s %6s\n" "Mem0 (self-hosted)" "125/192" "121.33 ± 10.97" "65.1%"
printf "%-20s %8s %15s %6s\n" "MD-файлы" "123/192" "123.67 ± 2.08"  "64.1%"
printf "%-20s %8s %15s %6s\n" "GitHub Issues" "122/192" "119.67 ± 12.66" "63.5%"
printf "%-20s %8s %15s %6s\n" "Helixir" "121/192" "118.00 ± 16.70" "63.0%"
echo ""
echo -e "${BLUE}Ключевой вывод:${NC} MD-файлы — самый стабильный baseline (σ=2.08)."
echo "Mem0 лидирует на задачах со сложным retrieval (S4, S8, S11)."
echo "Все подходы в узком диапазоне 63-65% — различия меньше LLM-дисперсии."
