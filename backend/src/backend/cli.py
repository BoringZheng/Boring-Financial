"""Management CLI for Boring Financial.

Commands:
    retry-all   Push all transactions with external-API issues back into
                the retry queue so the background worker retries them.
"""

from __future__ import annotations

import argparse

from backend.core.config import settings
from backend.services.retry_queue import requeue_all_external_api_failures


def cmd_retry_all() -> None:
    """Requeue every transaction whose auto_reason mentions 'external api'."""
    print(f"Database: {settings.database_url}")
    print("Scanning for transactions with external API issues ...")
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

    args = parser.parse_args()

    if args.command == "retry-all":
        cmd_retry_all()


if __name__ == "__main__":
    main()
