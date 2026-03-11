PYTHON ?= python3.11
COMPOSE ?= docker compose
PREBUILT_COMPOSE_FILES ?= -f docker-compose.yml -f docker-compose.prebuilt.yml

.PHONY: backend-dev frontend-dev build-frontend check-backend compose-up compose-up-prebuilt compose-up-prebuilt-classic compose-down compose-down-prebuilt compose-logs compose-logs-prebuilt compose-ps

backend-dev:
	cd web-demo/backend && ../../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

frontend-dev:
	cd web-demo && npm run dev -- --host 0.0.0.0 --port 5173

build-frontend:
	cd web-demo && npm run build

check-backend:
	$(PYTHON) -m py_compile utils.py fucker.py web-demo/backend/app.py

compose-up:
	$(COMPOSE) up -d --build

compose-up-prebuilt:
	$(COMPOSE) $(PREBUILT_COMPOSE_FILES) up -d --build

compose-up-prebuilt-classic:
	DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 $(COMPOSE) $(PREBUILT_COMPOSE_FILES) up -d --build

compose-down:
	$(COMPOSE) down

compose-down-prebuilt:
	$(COMPOSE) $(PREBUILT_COMPOSE_FILES) down

compose-logs:
	$(COMPOSE) logs -f

compose-logs-prebuilt:
	$(COMPOSE) $(PREBUILT_COMPOSE_FILES) logs -f

compose-ps:
	$(COMPOSE) $(PREBUILT_COMPOSE_FILES) ps
