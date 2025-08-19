# Backend Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (optional: ping for /api/monitor/ping)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -U pip && pip install -r /app/backend/requirements.txt

# Copy project files (only what's needed at runtime)
COPY backend /app/backend
COPY config /app/config
COPY scripts /app/scripts
COPY README.md /app/README.md

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
