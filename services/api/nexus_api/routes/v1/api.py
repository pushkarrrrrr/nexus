from fastapi import APIRouter

from services.api.nexus_api.ai.routes import ai_router
from services.api.nexus_api.auth.routes import auth_router
from services.api.nexus_api.goals.routes import goals_router
from services.api.nexus_api.sessions.routes import sessions_router
from services.api.nexus_api.tasks.routes import tasks_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(tasks_router)
v1_router.include_router(sessions_router)
v1_router.include_router(goals_router)
v1_router.include_router(ai_router)


@v1_router.get("/system/status")
async def system_status():
    return {
        "status": "ready",
        "phase": "phase_5_ai_gateway",
        "supported_surfaces": ["dashboard", "ambient"],
    }
