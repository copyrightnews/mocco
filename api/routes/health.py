"""Liveness check: confirms DB is reachable and reports uptime."""
from __future__ import annotations

import time
import os

import psycopg2
from fastapi import APIRouter

router = APIRouter()

_BOOT_TIME = time.time()


@router.get("/health")
def health():
    db_ok = "ok"
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=3)
        conn.close()
    except Exception as e:
        db_ok = f"error: {e.__class__.__name__}"
    return {"db": db_ok, "uptime_s": int(time.time() - _BOOT_TIME)}
