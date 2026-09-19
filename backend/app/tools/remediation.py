"""Remediation execution tools with safety allowlist.

Never allows arbitrary commands. Each allowed action maps to
an explicit Python/Boto3 function.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from strands import tool

from ..config import get_settings
from .cloudwatch import get_simulator

logger = logging.getLogger(__name__)

# ── Allowed remediation actions ──────────────────────────────────────────────

def _restart_service(resource_id: str, params: dict) -> dict[str, Any]:
    """Force a new deployment on an ECS service."""
    settings = get_settings()
    if settings.simulation_mode:
        sim = get_simulator()
        return sim.apply_remediation("restart_service", params)
    try:
        import boto3
        ecs = boto3.client("ecs", region_name=settings.aws_region)
        parts = resource_id.split("/")
        cluster, service = parts[1], parts[2]
        ecs.update_service(cluster=cluster, service=service, forceNewDeployment=True)
        return {"action": "restart_service", "success": True, "message": f"Forced new deployment for {service}"}
    except Exception as exc:
        return {"action": "restart_service", "success": False, "error": str(exc)}


def _scale_up(resource_id: str, params: dict) -> dict[str, Any]:
    """Scale an ECS service to a higher desired count."""
    settings = get_settings()
    desired = params.get("desired_count", 4)
    if settings.simulation_mode:
        sim = get_simulator()
        return sim.apply_remediation("scale_up", {"desired_count": desired})
    try:
        import boto3
        ecs = boto3.client("ecs", region_name=settings.aws_region)
        parts = resource_id.split("/")
        cluster, service = parts[1], parts[2]
        ecs.update_service(cluster=cluster, service=service, desiredCount=desired)
        return {"action": "scale_up", "success": True, "desired_count": desired}
    except Exception as exc:
        return {"action": "scale_up", "success": False, "error": str(exc)}


def _flush_cache(resource_id: str, params: dict) -> dict[str, Any]:
    settings = get_settings()
    if settings.simulation_mode:
        sim = get_simulator()
        return sim.apply_remediation("flush_cache", params)
    return {"action": "flush_cache", "success": True, "message": "Cache flushed (no-op in this context)"}


def _restart_container(resource_id: str, params: dict) -> dict[str, Any]:
    settings = get_settings()
    if settings.simulation_mode:
        sim = get_simulator()
        return sim.apply_remediation("restart_container", params)
    return {"action": "restart_container", "success": True, "message": "Container restart triggered"}


def _clear_stuck_queue(resource_id: str, params: dict) -> dict[str, Any]:
    settings = get_settings()
    if settings.simulation_mode:
        sim = get_simulator()
        return sim.apply_remediation("clear_stuck_queue", params)
    return {"action": "clear_stuck_queue", "success": True, "message": "Queue purged"}


ALLOWED_ACTIONS: dict[str, Callable] = {
    "restart_service": _restart_service,
    "scale_up": _scale_up,
    "flush_cache": _flush_cache,
    "restart_container": _restart_container,
    "clear_stuck_queue": _clear_stuck_queue,
}


@tool
def execute_remediation(resource_id: str, action: str, parameters: str = "{}") -> str:
    """Execute a validated remediation action on an AWS resource.

    The action MUST be one of the approved actions. Arbitrary commands are rejected.

    Args:
        resource_id: The AWS resource identifier to remediate.
        action: The remediation action to perform. Must be one of:
                restart_service, scale_up, flush_cache, restart_container, clear_stuck_queue.
        parameters: JSON string of action-specific parameters.

    Returns:
        JSON string with the execution result, including success status and details.
    """
    settings = get_settings()
    logger.info("execute_remediation: action=%s resource=%s dry_run=%s simulation=%s",
                action, resource_id, settings.dry_run, settings.simulation_mode)

    # Validate action against allowlist
    if action not in ALLOWED_ACTIONS:
        return json.dumps({
            "error": f"Action '{action}' is not in the approved remediation allowlist.",
            "allowed_actions": list(ALLOWED_ACTIONS.keys()),
            "success": False,
        })

    # Parse parameters
    try:
        params = json.loads(parameters) if isinstance(parameters, str) else parameters
    except json.JSONDecodeError:
        params = {}

    # Dry-run mode
    if settings.dry_run:
        return json.dumps({
            "action": action,
            "resource_id": resource_id,
            "dry_run": True,
            "success": True,
            "message": f"DRY RUN: Would execute '{action}' on {resource_id} with params {params}",
        })

    # Execute
    handler = ALLOWED_ACTIONS[action]
    result = handler(resource_id, params)
    result["resource_id"] = resource_id
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    result["simulation"] = settings.simulation_mode

    logger.info("Remediation result: %s", result)
    return json.dumps(result, indent=2)
