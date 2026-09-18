from fastapi import APIRouter

from services.api.nexus_api.auth.routes import auth_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)


@v1_router.get("/system/status")
async def system_status():
    return {
        "status": "ready",
        "phase": "phase_3_identity_and_user_context",
        "supported_surfaces": ["dashboard", "ambient"],
    }
