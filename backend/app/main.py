from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.database.connections import build_registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    registry = build_registry(
        timeout_seconds=settings.query_timeout_seconds,
        profile_budget_seconds=settings.profile_time_budget_seconds,
        config_path=settings.databases_config,
        default_url=settings.database_url,
        environ=dict(os.environ),
    )
    app.state.registry = registry
    yield
    for connection in registry.all():
        connection.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI SQL Analyst", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(router)
    return app


app = create_app()
