"""Health verification tools: check that remediation worked."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from strands import tool

from ..config import get_settings
from .cloudwatch import get_simulator

logger = logging.getLogger(__name__)


@tool
def verify_health_status(resource_id: str) -> str:
    """Verify the health of a resource after remediation.

    Checks CPU, memory, error rates, container restarts, latency,
    and CloudWatch alarm states to confirm recovery.

    Args:
        resource_id: The AWS resource to verify.

    Returns:
        JSON string with health status, individual checks, and metrics.
    """
    settings = get_settings()
    logger.info("verify_health_status for %s", resource_id)

    if settings.simulation_mode:
        sim = get_simulator()
        m = sim.current_metrics()

        checks: list[dict[str, Any]] = [
            {
                "name": "CPU Utilization",
                "status": "pass" if m.cpu_percent < 80 else "fail",
                "value": m.cpu_percent,
                "threshold": 80,
                "unit": "%",
            },
            {
                "name": "Memory Utilization",
                "status": "pass" if m.memory_percent < 85 else "fail",
                "value": m.memory_percent,
                "threshold": 85,
                "unit": "%",
            },
            {
                "name": "HTTP 5xx Rate",
                "status": "pass" if m.http_5xx_rate < 2.0 else "fail",
                "value": m.http_5xx_rate,
                "threshold": 2.0,
                "unit": "%",
            },
            {
                "name": "Container Restarts",
                "status": "pass" if m.container_restarts == 0 else "fail",
                "value": m.container_restarts,
                "threshold": 0,
                "unit": "count",
            },
            {
                "name": "Response Latency (p99)",
                "status": "pass" if m.latency_p99_ms < 500 else "fail",
                "value": m.latency_p99_ms,
                "threshold": 500,
                "unit": "ms",
            },
            {
                "name": "CloudWatch Alarm State",
                "status": "pass" if m.alarm_state == "OK" else "fail",
                "value": m.alarm_state,
                "threshold": "OK",
                "unit": "",
            },
            {
                "name": "Running Tasks",
                "status": "pass" if m.running_count >= m.desired_count else "fail",
                "value": m.running_count,
                "threshold": m.desired_count,
                "unit": "tasks",
            },
        ]

        healthy = all(c["status"] == "pass" for c in checks)
        if healthy:
            sim.mark_recovered()

        result = {
            "resource_id": resource_id,
            "healthy": healthy,
            "checks": checks,
            "metrics": {
                "cpu_percent": m.cpu_percent,
                "memory_percent": m.memory_percent,
                "http_5xx_rate": m.http_5xx_rate,
                "latency_p99_ms": m.latency_p99_ms,
                "container_restarts": m.container_restarts,
                "running_count": m.running_count,
                "desired_count": m.desired_count,
            },
            "verification_summary": (
                "All health checks passed. Service has recovered."
                if healthy else
                "Some health checks failed. Service may still be degraded."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulation": True,
        }
        return json.dumps(result, indent=2)

    # Production: real checks
    try:
        import boto3
        ecs = boto3.client("ecs", region_name=settings.aws_region)
        parts = resource_id.split("/")
        if len(parts) >= 3:
            cluster, service = parts[1], parts[2]
            resp = ecs.describe_services(cluster=cluster, services=[service])
            svc = resp["services"][0] if resp.get("services") else {}
            running = svc.get("runningCount", 0)
            desired = svc.get("desiredCount", 0)
            healthy = running >= desired > 0
            return json.dumps({
                "resource_id": resource_id,
                "healthy": healthy,
                "checks": [{"name": "Running Tasks", "status": "pass" if healthy else "fail",
                             "value": running, "threshold": desired}],
                "metrics": {"running_count": running, "desired_count": desired},
                "verification_summary": "Service healthy" if healthy else "Service degraded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "simulation": False,
            }, indent=2)
        return json.dumps({"error": "Unsupported resource format", "healthy": False, "simulation": False})
    except Exception as exc:
        return json.dumps({"error": str(exc), "healthy": False, "simulation": False})
