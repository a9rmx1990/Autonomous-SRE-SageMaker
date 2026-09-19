"""Infrastructure inspection tools: resource health and status."""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import tool

from ..config import get_settings
from .cloudwatch import get_simulator

logger = logging.getLogger(__name__)


@tool
def inspect_resource_health(resource_id: str) -> str:
    """Inspect the health of an AWS resource (ECS service, EC2, Lambda, etc.).

    Args:
        resource_id: Identifier of the AWS resource to inspect.

    Returns:
        JSON string with CPU, memory, container status, error rates, and health.
    """
    settings = get_settings()
    logger.info("inspect_resource_health for %s (simulation=%s)", resource_id, settings.simulation_mode)

    if settings.simulation_mode:
        sim = get_simulator()
        health = sim.resource_health()
        return json.dumps(health, indent=2)

    # Production: inspect via boto3
    try:
        import boto3
        # Attempt ECS service describe
        ecs = boto3.client("ecs", region_name=settings.aws_region)
        # Parse resource_id: expected format "ecs-service/{cluster}/{service}"
        parts = resource_id.split("/")
        if len(parts) >= 3 and parts[0] == "ecs-service":
            cluster, service = parts[1], parts[2]
            resp = ecs.describe_services(cluster=cluster, services=[service])
            svc = resp["services"][0] if resp.get("services") else {}
            return json.dumps({
                "resource_id": resource_id,
                "resource_type": "ECS Service",
                "desired_count": svc.get("desiredCount", 0),
                "running_count": svc.get("runningCount", 0),
                "status": svc.get("status", "UNKNOWN"),
                "simulation": False,
            }, indent=2)
        return json.dumps({"resource_id": resource_id, "error": "Unsupported resource type", "simulation": False})
    except Exception as exc:
        logger.error("Resource inspection error: %s", exc)
        return json.dumps({"error": str(exc), "resource_id": resource_id, "simulation": False})
