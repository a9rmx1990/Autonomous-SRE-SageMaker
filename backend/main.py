"""FastAPI application entry point for Autonomous SRE platform."""

import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("autonomous-sre")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Autonomous SRE & Self-Healing Cloud Swarm",
        description="Multi-agent AI platform for autonomous incident detection, investigation, remediation, and verification.",
        version=settings.version,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        logger.info("Autonomous SRE starting (simulation=%s, model=%s, region=%s)",
                     settings.simulation_mode, settings.bedrock_model_id, settings.aws_region)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
