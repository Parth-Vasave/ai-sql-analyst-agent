from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.schemas import HealthResponse
from app.config import Settings, get_settings
from app.database.connection import check_database

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    if check_database(settings):
        return HealthResponse(status="ok", database="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="degraded", database="unavailable")
