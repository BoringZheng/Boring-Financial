"""Management CLI for Boring Financial.

Commands:
    retry-all   Push all transactions with external-API issues back into
                the retry queue so the background worker retries them.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from backend.core.config import settings
from backend.db.runtime_schema import ensure_runtime_schema
from backend.db.session import SessionLocal
from backend.models import User
from backend.services.retry_queue import requeue_all_external_api_failures


def cmd_retry_all() -> None:
    """Requeue every transaction whose auto_reason mentions 'external api'."""
    print(f"Database: {settings.database_url}")
    print("Scanning for transactions with external API issues ...")
    ensure_runtime_schema()
    count = requeue_all_external_api_failures()
    if count == 0:
        print("No transactions found — nothing to do.")
    else:
        print(
            f"Done — {count} transaction(s) moved to retry queue. "
            f"The background worker will retry them one at a time "
            f"(max {settings.retry_queue_max_retries} retries, "
            f"{settings.retry_queue_delay_seconds}s delay between requests)."
        )


def cmd_make_admin(username: str) -> None:
    """Grant admin privileges to an existing user."""
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            raise SystemExit(f"User not found: {username}")
        user.is_admin = True
        db.commit()
        print(f"Done — {username} is now an admin.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bf-admin",
        description="Boring Financial management CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "retry-all",
        help="Push all external-API-failed transactions back to retry queue",
    )
    make_admin = sub.add_parser(
        "make-admin",
        help="Grant admin privileges to an existing user",
    )
    make_admin.add_argument("username")

    args = parser.parse_args()

    if args.command == "retry-all":
        cmd_retry_all()
    elif args.command == "make-admin":
        cmd_make_admin(args.username)


if __name__ == "__main__":
    main()
