from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")


@v1_router.get("/system/status")
async def system_status():
    return {
        "status": "ready",
        "phase": "phase_1_monorepo_foundation",
        "supported_surfaces": ["dashboard", "ambient"],
    }
