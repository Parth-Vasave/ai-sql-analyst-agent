"""Request IDs and structured (JSON) logging.

Every request gets an ID: the caller's X-Request-ID when it is a short safe token, otherwise a
new one. It is returned in the X-Request-ID response header, attached to every log line written
while the request is handled, and included in query results, so a user-visible answer can be
traced to its log lines.

Logs are one JSON object per line. They describe what happened (step, status, duration, error
category) and never carry secrets, connection URLs, the question text, SQL or result rows: log
fields go through `safe_fields`, which drops those keys.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
# Never logged, whatever a caller passes: content that may be personal or sensitive, and secrets.
_UNLOGGED_KEYS = frozenset(
    {"question", "sql", "rows", "answer", "url", "password", "api_key", "token", "secret", "authorization"}
)

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("app.request")


def current_request_id() -> str | None:
    return _request_id.get()


def new_request_id(candidate: str | None) -> str:
    """The caller's ID if it is a short safe token (it ends up in logs), otherwise a fresh one."""
    if candidate and _VALID_REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def safe_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if k.lower() not in _UNLOGGED_KEYS}


def log_event(log: logging.Logger, message: str, level: int = logging.INFO, **fields: Any) -> None:
    log.log(level, message, extra={"fields": safe_fields(fields)})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            entry["request_id"] = request_id
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    """JSON lines on stderr for the application's loggers."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app_logger = logging.getLogger("app")
    app_logger.handlers = [handler]
    app_logger.setLevel(level.upper())
    app_logger.propagate = False


def install(app: FastAPI) -> None:
    """Request-ID middleware and a generic handler for unexpected errors."""

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = new_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = _request_id.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Details go to the log, never to the client.
            logger.exception("unhandled error", extra={"fields": {"path": request.url.path}})
            response = JSONResponse(
                {"detail": "Internal server error.", "request_id": request_id}, status_code=500
            )
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            logger,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        _request_id.reset(token)
        return response
