# PO Copilot — atalhos de desenvolvimento.
# Equivalente ao dev.ps1, para quem roda make (Git Bash, WSL, macOS, Linux).

SHELL := /bin/sh
.PHONY: dev install test check-scaffold
.DEFAULT_GOAL := dev

# A API roda com o Python do venv: Scripts/ no Git Bash, bin/ no resto.
# Fica vazio enquanto o venv nao existe — o check-scaffold trata esse caso.
VENV_BIN := $(wildcard apps/api/.venv/bin/python apps/api/.venv/Scripts/python.exe)
VENV_PY  := $(CURDIR)/$(firstword $(VENV_BIN))

check-scaffold:
	missing=""; \
	[ -d apps/api ] || missing="$$missing apps/api"; \
	[ -d apps/web ] || missing="$$missing apps/web"; \
	if [ -n "$$missing" ]; then \
	  echo ""; \
	  echo "  Scaffold ausente."; \
	  echo ""; \
	  echo "  Faltando:$$missing"; \
	  echo ""; \
	  echo "  Veja docs/roadmap.md para o que entra em cada milestone."; \
	  echo ""; \
	  exit 1; \
	fi
	if [ -z "$(VENV_BIN)" ] || [ ! -d apps/web/node_modules ]; then \
	  echo ""; \
	  echo "  As dependencias ainda nao foram instaladas. Rode: make install"; \
	  echo ""; \
	  exit 1; \
	fi

## dev — sobe API (:8000) e web (:3000) em paralelo. Ctrl+C derruba os dois.
dev: check-scaffold
	@echo "-> API  em http://localhost:8000"
	@echo "-> Web  em http://localhost:3000"
	@echo ""
	@trap "kill 0" EXIT INT TERM; \
	( cd apps/api && "$(VENV_PY)" -m uvicorn app.main:app --reload --port 8000 ) & \
	( cd apps/web && npm run dev ) & \
	wait

## install — cria o venv da API e instala as dependencias dos dois apps.
install:
	python -m venv apps/api/.venv
	py=apps/api/.venv/bin/python; \
	[ -x "$$py" ] || py=apps/api/.venv/Scripts/python.exe; \
	"$$py" -m pip install -r apps/api/requirements.txt
	cd apps/web && npm install

## test — roda os testes da API.
test: check-scaffold
	cd apps/api && "$(VENV_PY)" -m pytest tests -q
