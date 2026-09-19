from fastapi import APIRouter

from services.api.nexus_api.agents.routes import agents_router
from services.api.nexus_api.ai.routes import ai_router
from services.api.nexus_api.auth.routes import auth_router
from services.api.nexus_api.goals.routes import goals_router
from services.api.nexus_api.graph.routes import graph_router
from services.api.nexus_api.knowledge.routes import knowledge_router
from services.api.nexus_api.memory.routes import memory_router
from services.api.nexus_api.sessions.routes import sessions_router
from services.api.nexus_api.tasks.routes import tasks_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(tasks_router)
v1_router.include_router(sessions_router)
v1_router.include_router(goals_router)
v1_router.include_router(ai_router)
v1_router.include_router(memory_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(graph_router)
v1_router.include_router(agents_router)


@v1_router.get("/system/status")
async def system_status():
    return {
        "status": "ready",
        "phase": "phase_8_agent_orchestrator",
        "supported_surfaces": ["dashboard", "ambient"],
    }
