"""LogAnalyst: specialist agent for investigating CloudWatch logs and metrics.

Exposed to the orchestrator as a Strands @tool.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import Agent, tool

from ..config import get_settings
from ..tools.cloudwatch import fetch_cloudwatch_alarms, fetch_cloudwatch_logs
from ..tools.infrastructure import inspect_resource_health

logger = logging.getLogger(__name__)

LOG_ANALYST_SYSTEM_PROMPT = """\
You are LogAnalyst, a specialist SRE agent focused on investigating
infrastructure incidents through log analysis and metric inspection.

Your job:
1. Examine CloudWatch alarms for the affected service.
2. Review CloudWatch logs for error patterns.
3. Inspect resource health (CPU, memory, container status).
4. Identify the probable root cause with supporting evidence.

Return your findings as a JSON object with these fields:
- probable_root_cause: string describing the root cause
- supporting_evidence: list of evidence strings
- affected_resources: list of affected AWS resource identifiers
- severity: one of "critical", "high", "medium", "low"
- confidence: float between 0.0 and 1.0
- recommended_action: string describing recommended remediation
- raw_metrics: dict of relevant metric values

Be thorough but concise. Only report findings supported by actual data.
Never fabricate metrics or log entries. If data is from simulation,
note that in your analysis.
"""


def create_log_analyst() -> Agent:
    """Create and return a LogAnalyst Strands agent."""
    settings = get_settings()
    return Agent(
        model=settings.bedrock_model_id,
        system_prompt=LOG_ANALYST_SYSTEM_PROMPT,
        tools=[fetch_cloudwatch_alarms, fetch_cloudwatch_logs, inspect_resource_health],
    )


@tool
def log_analyst_tool(service_name: str, incident_context: str) -> str:
    """Analyze logs and metrics for a service to find root cause.

    The LogAnalyst examines CloudWatch alarms, logs, and resource health
    to identify the probable root cause of an incident.

    Args:
        service_name: Name of the affected AWS service.
        incident_context: Description of the current incident symptoms.

    Returns:
        JSON string with findings: root cause, evidence, severity, and recommendation.
    """
    settings = get_settings()
    logger.info("LogAnalyst investigating service=%s", service_name)

    try:
        analyst = create_log_analyst()
        prompt = (
            f"Investigate the following incident for service '{service_name}':\n\n"
            f"{incident_context}\n\n"
            f"Use your tools to:\n"
            f"1. Check CloudWatch alarms for {service_name}\n"
            f"2. Fetch recent CloudWatch logs for {service_name}\n"
            f"3. Inspect the resource health of ecs-service/prod-ecs-cluster/{service_name}\n\n"
            f"Then provide your structured analysis as JSON."
        )
        response = analyst(prompt)
        result = str(response)
        logger.info("LogAnalyst completed investigation for %s", service_name)
        return result
    except Exception as exc:
        logger.error("LogAnalyst failed: %s", exc)
        # Return a structured fallback based on simulation data
        if settings.simulation_mode:
            from ..tools.cloudwatch import get_simulator
            sim = get_simulator()
            m = sim.current_metrics()
            fallback = {
                "probable_root_cause": (
                    f"CPU saturation ({m.cpu_percent}%) with container restart loop "
                    f"({m.container_restarts} restarts) causing HTTP 5xx spike ({m.http_5xx_rate}%)"
                ),
                "supporting_evidence": [
                    f"CPU utilization: {m.cpu_percent}% (threshold: 90%)",
                    f"Container restarts: {m.container_restarts} in last 10 minutes",
                    f"HTTP 5xx rate: {m.http_5xx_rate}%",
                    f"Latency p99: {m.latency_p99_ms}ms (baseline: ~65ms)",
                    f"Memory utilization: {m.memory_percent}%",
                    f"Running tasks: {m.running_count}/{m.desired_count}",
                    "CloudWatch alarm 'payment-api-cpu-high' in ALARM state",
                    "OOMKilled events detected in container logs",
                ],
                "affected_resources": [
                    f"ecs-service/prod-ecs-cluster/{service_name}",
                    f"cloudwatch-alarm/payment-api-cpu-high",
                ],
                "severity": "critical",
                "confidence": 0.92,
                "recommended_action": (
                    "Scale ECS service from 2 to 4 tasks to distribute load, "
                    "then investigate memory leak in TransactionProcessor"
                ),
                "raw_metrics": {
                    "cpu_percent": m.cpu_percent,
                    "memory_percent": m.memory_percent,
                    "http_5xx_rate": m.http_5xx_rate,
                    "container_restarts": m.container_restarts,
                    "latency_p99_ms": m.latency_p99_ms,
                },
                "simulation": True,
                "note": "Analysis generated from simulation data (Bedrock agent unavailable)",
            }
            return json.dumps(fallback, indent=2)
        return json.dumps({"error": str(exc), "probable_root_cause": "Unable to analyze", "confidence": 0.0})
