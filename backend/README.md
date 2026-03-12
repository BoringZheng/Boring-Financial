# Backend

FastAPI backend for Boring Financial.

## Quick Start

```bash
pip install -e .[dev]
copy .env.example .env
alembic upgrade head
uvicorn backend.main:app --reload
```
