from __future__ import annotations

from sqlalchemy import inspect, text

from backend.db.session import engine


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if "import_batches" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("import_batches")}
    statements: list[str] = []
    if "total_count" not in columns:
        statements.append("ALTER TABLE import_batches ADD COLUMN total_count INTEGER DEFAULT 0 NOT NULL")

    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" not in user_columns:
            statements.append("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE NOT NULL")

    if "transactions" in inspector.get_table_names():
        txn_columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "api_retry_count" not in txn_columns:
            statements.append("ALTER TABLE transactions ADD COLUMN api_retry_count INTEGER DEFAULT 0 NOT NULL")
        if "api_retry_provider" not in txn_columns:
            statements.append("ALTER TABLE transactions ADD COLUMN api_retry_provider VARCHAR(64)")
        if "api_retry_last_error" not in txn_columns:
            statements.append("ALTER TABLE transactions ADD COLUMN api_retry_last_error TEXT")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
