import os
import tempfile
from mocco.migrate import apply_migrations, ensure_schema_migrations_table, _applied_versions


def test_ensure_schema_migrations_table_creates_when_missing():
    # Use a fresh in-memory-ish sqlite via tempdir is overkill; instead, test idempotency.
    # We rely on the caller to pass a connection; here we test against a real Postgres if DATABASE_URL is set.
    import psycopg2
    if not os.environ.get("DATABASE_URL"):
        return  # skip when no DB
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        ensure_schema_migrations_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_migrations')")
            assert cur.fetchone()[0] is not None
    finally:
        conn.close()


def test_apply_migrations_records_versions():
    import psycopg2
    if not os.environ.get("DATABASE_URL"):
        return
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        # Drop and recreate to test fresh apply
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS schema_migrations")
            cur.execute("""
                CREATE TABLE users (
                    id bigint PRIMARY KEY,
                    telegram_id bigint UNIQUE NOT NULL
                )
            """)
        conn.commit()
        apply_migrations(conn, "src/mocco/migrations")
        applied = _applied_versions(conn)
        assert "001_tma_profile_fields" in applied
        # The new columns must exist
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
            cols = {r[0] for r in cur.fetchall()}
        assert {"gender", "age", "location", "occupation", "interests", "timezone", "language"}.issubset(cols)
    finally:
        conn.close()
