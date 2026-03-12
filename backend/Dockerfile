FROM python:3.12-slim

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/README.md /app/README.md
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/src /app/src
COPY category_map.csv /app/category_map.csv

RUN pip install --no-cache-dir -e .

ENV PYTHONPATH=/app/src

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
