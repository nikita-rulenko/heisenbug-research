.PHONY: help start stop restart status logs run \
        bench bench-approach bench-baseline \
        bench-tw bench-tw-approach bench-full \
        portal-status portal-baseline-tests scratch-clean

PORT    ?= 8765
HOST    ?= 127.0.0.1
PYTHON  ?= python3
DIR     := $(shell pwd)
PIDFILE := $(DIR)/.server.pid
LOGFILE := $(DIR)/.server.log

# Coffee-portal location (override if cloned elsewhere)
PORTAL_DIR ?= $(HOME)/Downloads/heisenbug-coffee-portal

# Benchmark defaults (override on the make command-line)
APPROACH ?= md_files
TOPIC    ?= both
NUM_RUNS ?= 3

help:
	@echo "Context Recovery — full control plane"
	@echo ""
	@echo "── server (live dashboard) ───────────────────────────────────"
	@echo "  make start                — launch server in background"
	@echo "  make stop                 — stop background server"
	@echo "  make restart              — stop then start"
	@echo "  make status / logs / run  — diagnostics / foreground server"
	@echo "  dashboards: http://$(HOST):$(PORT)/   (v1)"
	@echo "              http://$(HOST):$(PORT)/v2 (v2)"
	@echo ""
	@echo "── core benchmark (recovery Q&A) ─────────────────────────────"
	@echo "  make bench                            — all 4 approaches"
	@echo "  make bench-approach APPROACH=mem0     — single approach"
	@echo "  make bench-baseline                   — regenerate baseline.jsonl"
	@echo ""
	@echo "── test-writing stage (off-dashboard) ────────────────────────"
	@echo "  make bench-tw                         — all approaches × TOPIC (default: both)"
	@echo "  make bench-tw-approach APPROACH=helixir_mcp TOPIC=fixed|wide|free|both|all"
	@echo "  make bench-full                       — bench + bench-tw (TOPIC=all gives all 3)"
	@echo "    TOPIC modes:"
	@echo "      fixed = Order.CalculateTotal (same for all approaches → direct compare)"
	@echo "      wide  = random pick from 5-topic curated pool, seeded by approach"
	@echo "      free  = agent picks own target from context (subjective judge, max=20)"
	@echo "      both  = fixed + wide  (default)"
	@echo "      all   = fixed + wide + free"
	@echo ""
	@echo "── safety / housekeeping ─────────────────────────────────────"
	@echo "  make portal-status                    — git status of coffee-portal"
	@echo "  make portal-baseline-tests            — record baseline 'go test ./...'"
	@echo "  make scratch-clean                    — sweep zz_bench_*_test.go"
	@echo ""
	@echo "Variables: APPROACH, TOPIC, NUM_RUNS, PORTAL_DIR (override on cmdline)"

start:
	@if [ -f $(PIDFILE) ] && kill -0 $$(cat $(PIDFILE)) 2>/dev/null; then \
		echo "already running (pid $$(cat $(PIDFILE)))"; \
	else \
		lsof -iTCP:$(PORT) -sTCP:LISTEN -t 2>/dev/null | xargs -r kill -TERM 2>/dev/null || true; \
		sleep 0.3; \
		nohup $(PYTHON) $(DIR)/server.py --host $(HOST) --port $(PORT) > $(LOGFILE) 2>&1 & \
		echo $$! > $(PIDFILE); \
		sleep 0.5; \
		echo "started: pid $$(cat $(PIDFILE))"; \
		echo "  v1: http://$(HOST):$(PORT)/"; \
		echo "  v2: http://$(HOST):$(PORT)/v2"; \
	fi

stop:
	@if [ -f $(PIDFILE) ]; then \
		pid=$$(cat $(PIDFILE)); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -TERM $$pid && echo "stopped pid $$pid"; \
		else \
			echo "pidfile stale (pid $$pid not running)"; \
		fi; \
		rm -f $(PIDFILE); \
	else \
		echo "no pidfile — checking port $(PORT)..."; \
	fi
	@lsof -iTCP:$(PORT) -sTCP:LISTEN -t 2>/dev/null | xargs -r kill -TERM 2>/dev/null || true

restart: stop
	@sleep 0.3
	@$(MAKE) start

status:
	@echo "── port $(PORT) ──"
	@lsof -iTCP:$(PORT) -sTCP:LISTEN -P -n 2>/dev/null || echo "  not listening"
	@echo "── pidfile ──"
	@if [ -f $(PIDFILE) ]; then echo "  $(PIDFILE): pid $$(cat $(PIDFILE))"; else echo "  (none)"; fi

logs:
	@test -f $(LOGFILE) && tail -f $(LOGFILE) || echo "no log at $(LOGFILE)"

run:
	$(PYTHON) $(DIR)/server.py --host $(HOST) --port $(PORT)

# ── core benchmark ──────────────────────────────────────────────────
# Runs all 4 approaches × verification (no test-writing). This is what
# feeds the dashboard and produces recovery_*.json reference data.
bench:
	@$(MAKE) -s _check-portal-clean
	$(PYTHON) $(DIR)/runner.py all --num-runs $(NUM_RUNS)

bench-approach:
	@$(MAKE) -s _check-portal-clean
	$(PYTHON) $(DIR)/runner.py $(APPROACH) --num-runs $(NUM_RUNS)

bench-baseline:
	$(PYTHON) $(DIR)/tools/build_baseline.py

# ── test-writing stage ──────────────────────────────────────────────
# Writes a Go test against an EXISTING method in coffee-portal, runs it,
# scores via DeepSeek judge, then `git reset --hard HEAD && git clean -fd`
# the portal. NOT shown on dashboard.
#
# Pre-condition: portal must be clean (we check + abort if dirty).
bench-tw:
	@$(MAKE) -s _check-portal-clean
	@for a in md_files github_issues mem0 helixir_mcp; do \
		echo "── test-writing: $$a ──"; \
		$(PYTHON) $(DIR)/test_writing.py --approach $$a --topics $(TOPIC) || \
			echo "[bench-tw] $$a failed (continuing)"; \
	done

bench-tw-approach:
	@$(MAKE) -s _check-portal-clean
	$(PYTHON) $(DIR)/test_writing.py --approach $(APPROACH) --topics $(TOPIC)

bench-full:
	@$(MAKE) -s _check-portal-clean
	$(PYTHON) $(DIR)/runner.py all --num-runs $(NUM_RUNS) --with-test-writing --topics $(TOPIC)

# ── safety / housekeeping ───────────────────────────────────────────
# Internal: abort if portal has uncommitted changes (would be wiped by
# the rollback in test_writing.py, which is unacceptable).
_check-portal-clean:
	@if [ -n "$$(git -C $(PORTAL_DIR) status --porcelain)" ]; then \
		echo "ERROR: $(PORTAL_DIR) is dirty. Commit or stash first:"; \
		git -C $(PORTAL_DIR) status --short; \
		exit 1; \
	fi

portal-status:
	@echo "── $(PORTAL_DIR) ──"
	@git -C $(PORTAL_DIR) status --short || echo "(no git repo at $(PORTAL_DIR))"
	@echo "── HEAD ──"
	@git -C $(PORTAL_DIR) log --oneline -1

# Record the baseline `go test ./...` result. Used as a reference to
# detect collateral damage from LLM-written tests (regressions in
# unrelated tests). Refreshes if older than 24h.
PORTAL_TEST_BASELINE := $(DIR)/results/portal_test_baseline.txt
portal-baseline-tests:
	@mkdir -p $(DIR)/results
	@echo "Recording baseline 'go test ./...' in $(PORTAL_DIR)…"
	@cd $(PORTAL_DIR) && go test ./... 2>&1 | tee $(PORTAL_TEST_BASELINE) | tail -5
	@echo "Saved → $(PORTAL_TEST_BASELINE)"

# Aggressive sweep: only invoke if a test-writing run died mid-flight
# and left a scratch file behind. Normal runs clean themselves up via
# `git reset --hard HEAD && git clean -fd`.
scratch-clean:
	@found=$$(find $(PORTAL_DIR)/internal -name 'zz_bench_*_test.go' 2>/dev/null); \
	if [ -z "$$found" ]; then \
		echo "no scratch files found in $(PORTAL_DIR)/internal/"; \
	else \
		echo "removing:"; echo "$$found"; \
		echo "$$found" | xargs rm -f; \
	fi
