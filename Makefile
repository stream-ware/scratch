PY?=python3
VENV=.venv

.PHONY: setup run-backend

setup:
	$(PY) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -U pip && pip install -r backend/requirements.txt

run-backend:
	. $(VENV)/bin/activate && uvicorn backend.main:app --reload --port 8000

.PHONY: run-frontend
run-frontend:
	$(PY) -m http.server -d frontend 5173
