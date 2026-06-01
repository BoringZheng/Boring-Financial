# Backend

FastAPI backend for Boring Financial. This backend is managed with `uv`; use `uv.lock` as the dependency lock file.

## Quick Start: SQLite

Use this mode for local demo and development when PostgreSQL/Redis are not required.

PowerShell:

```powershell
Copy-Item .env.bare.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

Bash:

```bash
cp .env.bare.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

## Quick Start: PostgreSQL + Redis

Start dependencies from the repository root:

```bash
cd infra
docker compose up -d postgres redis
```

Then start the backend from `backend/`:

PowerShell:

```powershell
Copy-Item .env.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

Bash:

```bash
cp .env.example .env
uv sync --extra dev
uv run uvicorn backend.main:app --reload
```

## Common Commands

```bash
uv run pytest
uv run pytest --cov=backend
uv run alembic upgrade head
```

## Notes

- `uv sync --extra dev` creates and maintains the local `.venv` from `pyproject.toml` and `uv.lock`.
- The app creates runtime tables on startup via SQLAlchemy metadata, so Alembic is not required for local quick start.
- Alembic config remains in the project for future migration versioning.
- Health check: `http://127.0.0.1:8000/health`.
