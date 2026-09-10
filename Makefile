# PO Copilot — atalhos de desenvolvimento.
# Equivalente ao dev.ps1, para quem roda make (Git Bash, WSL, macOS, Linux).
#
# Os alvos so funcionam a partir do M0 (14/09/2026), quando apps/api e apps/web
# passam a existir. Antes disso o guard abaixo para com uma mensagem explicita.

SHELL := /bin/sh
.PHONY: dev install check-scaffold
.DEFAULT_GOAL := dev

check-scaffold:
	@missing=""; \
	[ -d apps/api ] || missing="$$missing apps/api"; \
	[ -d apps/web ] || missing="$$missing apps/web"; \
	if [ -n "$$missing" ]; then \
	  echo ""; \
	  echo "  Ambiente de dev ainda nao existe."; \
	  echo ""; \
	  echo "  Faltando:$$missing"; \
	  echo ""; \
	  echo "  Isso e esperado antes do M0. O scaffold do FastAPI e do Next.js"; \
	  echo "  e a primeira tarefa do M0, em 14/09/2026. Ate la apps/ fica vazio"; \
	  echo "  de proposito e nao ha o que subir nem o que instalar."; \
	  echo ""; \
	  echo "  Veja docs/roadmap.md para o que entra em cada milestone."; \
	  echo ""; \
	  exit 1; \
	fi

## dev — sobe API (:8000) e web (:3000) em paralelo. Ctrl+C derruba os dois.
dev: check-scaffold
	@echo "-> API  em http://localhost:8000"
	@echo "-> Web  em http://localhost:3000"
	@echo ""
	@trap "kill 0" EXIT INT TERM; \
	( cd apps/api && python -m uvicorn app.main:app --reload --port 8000 ) & \
	( cd apps/web && npm run dev ) & \
	wait

## install — instala as dependencias da API e do web.
install: check-scaffold
	cd apps/api && python -m pip install -r requirements.txt
	cd apps/web && npm install
