FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000

# Run migrations then start the server.
# alembic upgrade head is idempotent — safe to run on every container start.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
