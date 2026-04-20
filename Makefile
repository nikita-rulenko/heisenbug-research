# Heisenbug Research — benchmark & dashboard harness
# ---------------------------------------------------
# Usage:
#   make help         — list all targets
#   make bench        — run full context-recovery benchmark in background
#   make bench-stop   — kill a running benchmark
#   make bench-status — is the benchmark running? last exit code?
#   make bench-tail   — follow benchmark log
#   make bench-results— print Part A/B/C breakdown for last run
#   make server       — start dashboard server in background
#   make server-stop  — stop dashboard server
#   make server-tail  — follow dashboard server log
# ---------------------------------------------------

SHELL := /bin/bash
REPO_ROOT := $(shell pwd)
BENCH_PID_FILE := /tmp/heisenbug_bench.pid
BENCH_LOG := /tmp/heisenbug_bench.log
BENCH_EXIT_FILE := /tmp/heisenbug_bench.exit
SERVER_PID_FILE := /tmp/heisenbug_server.pid
SERVER_LOG := /tmp/heisenbug_server.log
SERVER_PORT := 8765

# Extract CEREBRAS_API_KEY from ~/.zshrc (export … form)
CEREBRAS_KEY := $(shell grep -E '^export CEREBRAS_API_KEY' $$HOME/.zshrc 2>/dev/null | head -1 | sed -E 's/^export CEREBRAS_API_KEY=["'\'']?([^"'\'']*)["'\'']?.*/\1/')

.PHONY: help bench bench-stop bench-status bench-tail bench-results \
        server server-stop server-tail

help:
	@echo "heisenbug-research harness"
	@echo ""
	@echo "  make bench          — start benchmark in background"
	@echo "  make bench-stop     — kill running benchmark"
	@echo "  make bench-status   — show bench status + last exit"
	@echo "  make bench-tail     — tail -f benchmark log"
	@echo "  make bench-results  — Part A/B/C breakdown for last run"
	@echo ""
	@echo "  make server         — start dashboard on :$(SERVER_PORT)"
	@echo "  make server-stop    — kill dashboard"
	@echo "  make server-tail    — tail -f dashboard log"
	@echo ""
	@echo "Logs: $(BENCH_LOG)  $(SERVER_LOG)"

# ───── Benchmark ────────────────────────────────────────────

bench:
	@if [ -f $(BENCH_PID_FILE) ] && kill -0 $$(cat $(BENCH_PID_FILE)) 2>/dev/null; then \
		echo "bench already running (PID $$(cat $(BENCH_PID_FILE)))"; exit 1; \
	fi
	@if [ -z "$(CEREBRAS_KEY)" ]; then \
		echo "ERROR: CEREBRAS_API_KEY not found in ~/.zshrc"; exit 1; \
	fi
	@echo "Starting benchmark → $(BENCH_LOG)"
	@rm -f $(BENCH_EXIT_FILE)
	@cd $(REPO_ROOT) && \
		( CEREBRAS_API_KEY="$(CEREBRAS_KEY)" python3 benchmarks/context_recovery/runner.py all \
			> $(BENCH_LOG) 2>&1 ; echo $$? > $(BENCH_EXIT_FILE) ) & \
		echo $$! > $(BENCH_PID_FILE)
	@sleep 1
	@echo "PID: $$(cat $(BENCH_PID_FILE))"
	@echo "Tail:  make bench-tail"
	@echo "Stop:  make bench-stop"

bench-stop:
	@if [ -f $(BENCH_PID_FILE) ]; then \
		PID=$$(cat $(BENCH_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Killing bench PID $$PID and children..."; \
			pkill -P $$PID 2>/dev/null; \
			kill -TERM $$PID 2>/dev/null; \
			sleep 2; \
			kill -KILL $$PID 2>/dev/null; \
			echo "stopped"; \
		else \
			echo "PID $$PID not running"; \
		fi; \
		rm -f $(BENCH_PID_FILE); \
	else \
		echo "no pid file — nothing to stop"; \
	fi

bench-status:
	@if [ -f $(BENCH_PID_FILE) ] && kill -0 $$(cat $(BENCH_PID_FILE)) 2>/dev/null; then \
		PID=$$(cat $(BENCH_PID_FILE)); \
		RUNTIME=$$(ps -p $$PID -o etime= 2>/dev/null | tr -d ' '); \
		LAST=$$(tail -1 $(BENCH_LOG) 2>/dev/null); \
		echo "RUNNING  PID=$$PID  elapsed=$$RUNTIME"; \
		echo "Last line: $$LAST"; \
	else \
		if [ -f $(BENCH_EXIT_FILE) ]; then \
			echo "FINISHED  exit=$$(cat $(BENCH_EXIT_FILE))"; \
		else \
			echo "NOT RUNNING"; \
		fi; \
	fi

bench-tail:
	@tail -f $(BENCH_LOG)

bench-results:
	@python3 -c "import json; \
d=json.load(open('$(REPO_ROOT)/benchmarks/results/recovery_comparison.json')); \
print(f\"{'approach':<16} {'A':>6} {'B':>6} {'C':>6} {'total':>8}\"); \
[print(f\"{k:<16} {v.get('part_a_pct','-'):>6} {v.get('part_b_pct','-'):>6} {v.get('part_c_pct','-'):>6} {v.get('accuracy_pct','-'):>7}%\") for k,v in d.get('approaches',{}).items()]"

# ───── Dashboard server ─────────────────────────────────────

server:
	@if [ -f $(SERVER_PID_FILE) ] && kill -0 $$(cat $(SERVER_PID_FILE)) 2>/dev/null; then \
		echo "server already running (PID $$(cat $(SERVER_PID_FILE)))"; exit 1; \
	fi
	@if lsof -iTCP:$(SERVER_PORT) -sTCP:LISTEN -n -P >/dev/null 2>&1; then \
		echo "Port $(SERVER_PORT) already in use. Run: make server-stop"; exit 1; \
	fi
	@if [ -z "$(CEREBRAS_KEY)" ]; then \
		echo "WARNING: CEREBRAS_API_KEY missing — modal will appear in UI"; \
	fi
	@echo "Starting dashboard → http://127.0.0.1:$(SERVER_PORT)/dashboard_recovery.html"
	@cd $(REPO_ROOT) && \
		CEREBRAS_API_KEY="$(CEREBRAS_KEY)" python3 benchmarks/context_recovery/server.py \
			> $(SERVER_LOG) 2>&1 & \
		echo $$! > $(SERVER_PID_FILE)
	@sleep 2
	@echo "PID: $$(cat $(SERVER_PID_FILE))"
	@echo "URL:   http://127.0.0.1:$(SERVER_PORT)/dashboard_recovery.html"

server-stop:
	@if [ -f $(SERVER_PID_FILE) ]; then \
		PID=$$(cat $(SERVER_PID_FILE)); \
		kill -TERM $$PID 2>/dev/null; \
		sleep 1; \
		kill -KILL $$PID 2>/dev/null; \
		rm -f $(SERVER_PID_FILE); \
		echo "server stopped"; \
	else \
		pkill -f 'benchmarks/context_recovery/server.py' 2>/dev/null && echo "server processes killed" || echo "no server running"; \
	fi

server-tail:
	@tail -f $(SERVER_LOG)
