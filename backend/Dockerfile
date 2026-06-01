FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /uvx /bin/

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/uv.lock /app/uv.lock
COPY backend/README.md /app/README.md
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/src /app/src
COPY category_map.csv /app/category_map.csv

RUN uv sync --frozen --no-dev

ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:${PATH}"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
