FROM python:3.12-slim

WORKDIR /app

# Build tools required to compile asyncpg (a C extension) from source.
# libpq-dev provides PostgreSQL client headers needed by some drivers.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install uv

# Copy dependency manifest first (better Docker layer caching)
COPY pyproject.toml .

# Install dependencies into the system Python (no venv needed in Docker)
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000

# Run migrations then start the server.
# alembic upgrade head is idempotent — safe to run on every container start.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
