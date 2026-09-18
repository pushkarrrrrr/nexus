from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from packages.config.nexus_config import get_settings
from packages.shared.nexus_shared.logging import configure_logging, get_logger
from services.api.nexus_api.database import close_database, init_database
from services.api.nexus_api.middleware import LoggingAndTraceMiddleware
from services.api.nexus_api.routes.health import router as health_router
from services.api.nexus_api.routes.v1.api import v1_router
from services.api.nexus_api.websocket import ws_router

logger = get_logger("nexus.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level, json_format=(settings.nexus_env == "production")
    )
    logger.info("nexus_api_starting", env=settings.nexus_env, port=settings.api_port)

    # Initialize DB connection pool
    await init_database()

    yield

    # Clean shutdown
    logger.info("nexus_api_shutting_down")
    await close_database()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="NEXUS Core API",
        description="Core API & Event Bus for NEXUS Agentic AI Operating System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Tracing & Logging Middleware
    app.add_middleware(LoggingAndTraceMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount Routers
    app.include_router(health_router)
    app.include_router(v1_router)
    app.include_router(ws_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "services.api.nexus_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.nexus_env == "development"),
    )
