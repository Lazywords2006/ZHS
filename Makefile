PYTHON ?= python3.11
COMPOSE ?= docker compose

.PHONY: backend-dev frontend-dev build-frontend check-backend compose-up compose-down compose-logs

backend-dev:
	cd web-demo/backend && ../../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

frontend-dev:
	cd web-demo && npm run dev -- --host 0.0.0.0 --port 5173

build-frontend:
	cd web-demo && npm run build

check-backend:
	$(PYTHON) -m py_compile web-demo/backend/app.py

compose-up:
	$(COMPOSE) up -d --build

compose-down:
	$(COMPOSE) down

compose-logs:
	$(COMPOSE) logs -f
