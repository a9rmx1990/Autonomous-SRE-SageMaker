"""Application settings loaded from environment variables."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration for the Autonomous SRE platform."""

    # AWS
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_profile: str | None = Field(default=None, alias="AWS_PROFILE")

    # Bedrock
    bedrock_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514",
        alias="BEDROCK_MODEL_ID",
    )

    # AgentCore Memory
    agentcore_memory_id: str | None = Field(default=None, alias="AGENTCORE_MEMORY_ID")

    # Application
    simulation_mode: bool = Field(default=True, alias="SIMULATION_MODE")
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_name: str = "autonomous-sre"
    version: str = "1.0.0"

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="CORS_ORIGINS",
    )

    # Observability
    otel_enabled: bool = Field(default=True, alias="OTEL_ENABLED")
    otel_endpoint: str = Field(
        default="http://localhost:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    xray_enabled: bool = Field(default=False, alias="XRAY_ENABLED")

    # Remediation
    max_remediation_attempts: int = 3
    remediation_cooldown_seconds: int = 60
    auto_approve_simulation: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
