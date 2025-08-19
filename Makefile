PY?=python3
VENV=.venv

.PHONY: setup backend

setup:
	$(PY) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -U pip && pip install -r backend/requirements.txt

backend:
	. $(VENV)/bin/activate && uvicorn backend.main:app --reload --port 8000

.PHONY: frontend
frontend:
	$(PY) -m http.server -d frontend 5173

.PHONY: docker-build docker-up docker-down docker-logs
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend
