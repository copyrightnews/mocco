"""Sequential, idempotent SQL migration runner.

Reads `*.sql` files from a directory in lexical order, applies any not yet
recorded in the `schema_migrations` table, and records them on success.
"""
from __future__ import annotations

import os
from pathlib import Path


def ensure_schema_migrations_table(conn) -> None:
    """Create the schema_migrations bookkeeping table if missing."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     text PRIMARY KEY,
                applied_at  timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    conn.commit()


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {r["version"] for r in cur.fetchall()}


def apply_migrations(conn, migrations_dir: str | os.PathLike) -> list[str]:
    """Apply any unapplied SQL files in `migrations_dir` in lexical order.

    Returns the list of versions that were applied in this call.
    """
    ensure_schema_migrations_table(conn)
    applied = _applied_versions(conn)
    new_versions: list[str] = []
    path = Path(migrations_dir)
    if not path.exists():
        return new_versions
    for sql_file in sorted(path.glob("*.sql")):
        version = sql_file.stem  # e.g. "001_tma_profile_fields"
        if version in applied:
            continue
        sql = sql_file.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
        conn.commit()
        new_versions.append(version)
    return new_versions
