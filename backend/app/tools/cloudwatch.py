"""CloudWatch tools: fetch alarms and logs for a given service.

When SIMULATION_MODE is enabled, returns data from the simulation engine.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import tool

from ..config import get_settings
from ..simulation.payment_incident import PaymentIncidentSimulator

logger = logging.getLogger(__name__)

# Module-level simulator (shared by the running process).
_simulator: PaymentIncidentSimulator | None = None


def get_simulator() -> PaymentIncidentSimulator:
    global _simulator
    if _simulator is None:
        _simulator = PaymentIncidentSimulator()
    return _simulator


def reset_simulator() -> PaymentIncidentSimulator:
    global _simulator
    _simulator = PaymentIncidentSimulator()
    return _simulator


@tool
def fetch_cloudwatch_alarms(service_name: str) -> str:
    """Fetch active CloudWatch alarms for a service.

    Args:
        service_name: Name of the AWS service to check alarms for.

    Returns:
        JSON string containing alarm data with state, thresholds, and current values.
    """
    settings = get_settings()
    logger.info("fetch_cloudwatch_alarms called for %s (simulation=%s)", service_name, settings.simulation_mode)

    if settings.simulation_mode:
        sim = get_simulator()
        alarms = sim.cloudwatch_alarms()
        return json.dumps({"alarms": alarms, "simulation": True}, indent=2)

    # Production: use boto3
    try:
        import boto3
        cw = boto3.client("cloudwatch", region_name=settings.aws_region)
        paginator = cw.get_paginator("describe_alarms")
        alarms = []
        for page in paginator.paginate():
            for alarm in page.get("MetricAlarms", []):
                if service_name.lower() in alarm.get("AlarmName", "").lower():
                    alarms.append({
                        "alarm_name": alarm["AlarmName"],
                        "state": alarm["StateValue"],
                        "metric": alarm.get("MetricName"),
                        "threshold": alarm.get("Threshold"),
                        "service": service_name,
                        "simulation": False,
                    })
        return json.dumps({"alarms": alarms, "simulation": False}, indent=2)
    except Exception as exc:
        logger.error("CloudWatch API error: %s", exc)
        return json.dumps({"error": str(exc), "alarms": [], "simulation": False})


@tool
def fetch_cloudwatch_logs(service_name: str, incident_context: str = "") -> str:
    """Fetch recent CloudWatch log entries for a service.

    Args:
        service_name: Name of the AWS service whose logs to retrieve.
        incident_context: Optional context about the current incident.

    Returns:
        JSON string containing log entries with timestamps, levels, and messages.
    """
    settings = get_settings()
    logger.info("fetch_cloudwatch_logs for %s", service_name)

    if settings.simulation_mode:
        sim = get_simulator()
        logs = sim.cloudwatch_logs()
        return json.dumps({"logs": logs, "count": len(logs), "simulation": True}, indent=2)

    try:
        import boto3
        logs_client = boto3.client("logs", region_name=settings.aws_region)
        log_group = f"/ecs/{service_name}"
        resp = logs_client.filter_log_events(
            logGroupName=log_group,
            limit=50,
            interleaved=True,
        )
        entries = [
            {"timestamp": e.get("timestamp"), "message": e.get("message", ""), "source": log_group}
            for e in resp.get("events", [])
        ]
        return json.dumps({"logs": entries, "count": len(entries), "simulation": False}, indent=2)
    except Exception as exc:
        logger.error("CloudWatch Logs error: %s", exc)
        return json.dumps({"error": str(exc), "logs": [], "simulation": False})
