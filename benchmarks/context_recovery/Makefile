.PHONY: help start stop restart status logs run

PORT    ?= 8765
HOST    ?= 127.0.0.1
PYTHON  ?= python3
DIR     := $(shell pwd)
PIDFILE := $(DIR)/.server.pid
LOGFILE := $(DIR)/.server.log

help:
	@echo "Context Recovery dashboard server"
	@echo ""
	@echo "  make start      — launch server in background (http://$(HOST):$(PORT)/)"
	@echo "  make stop       — stop background server"
	@echo "  make restart    — stop then start"
	@echo "  make status     — show listening socket + pid"
	@echo "  make logs       — tail server log"
	@echo "  make run        — run server in foreground (Ctrl+C to stop)"
	@echo ""
	@echo "  dashboards: http://$(HOST):$(PORT)/   (v1)"
	@echo "              http://$(HOST):$(PORT)/v2 (v2)"

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
