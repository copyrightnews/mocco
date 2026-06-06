"""FastAPI app factory for the Mocco TMA API."""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Make the bot package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mocco.config import load_config
from mocco.db import init_db

from api.errors import install_error_handlers
from api.routes import health, me, profile, models, keys, history, chat


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("mocco.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    cfg = load_config()
    init_db()
    logger.info("Mocco TMA API started.")
    yield
    logger.info("Mocco TMA API shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(title="Mocco TMA API", version="0.1.0", lifespan=lifespan)

    # CORS: TMA is a Telegram webview; allow the Vercel origin and localhost for dev.
    origins = [o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    install_error_handlers(app)

    app.include_router(health.router, prefix="/v1")
    # me, profile, models, keys, history, chat are added in later tasks.
    return app


app = create_app()
