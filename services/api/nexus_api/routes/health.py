from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from packages.config.nexus_config import get_settings
from services.api.nexus_api.database import check_db_health

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    database_healthy: bool
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    settings = get_settings()
    is_db_healthy, db_status = await check_db_health()

    overall_status = "ok" if is_db_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        environment=settings.nexus_env,
        database=db_status,
        database_healthy=is_db_healthy,
        timestamp=datetime.now(UTC).isoformat(),
    )
