FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first so this layer is cached unless deps change
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY data/ ./data/

ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["sh", "-c", "uv run python scripts/init_db.py && uv run python scripts/create_tables.py && uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
