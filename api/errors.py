"""ApiError + centralized handlers for the TMA API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("mocco.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict[str, Any] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        out = {"code": self.code, "message": self.message}
        out.update(self.extra)
        return {"error": out}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=exc.to_dict())

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal", "message": "Internal server error."}},
        )
