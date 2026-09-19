"""Verifier: specialist agent for post-remediation health checks."""

from __future__ import annotations

import json
import logging

from strands import Agent, tool

from ..config import get_settings
from ..tools.verification import verify_health_status

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """\
You are Verifier, a specialist SRE agent responsible for confirming
that a remediation action has successfully restored service health.

Check:
1. CPU utilization is below safe thresholds
2. Memory utilization is normal
3. HTTP 5xx error rate has dropped
4. Container restarts have stopped
5. Response latency is within SLO
6. CloudWatch alarms have returned to OK
7. Running task count matches desired count

Return your assessment as a JSON object:
- healthy: boolean
- checks: list of individual check results
- metrics: dict of current metric values
- verification_summary: string summary
- timestamp: ISO timestamp
"""


def create_verifier() -> Agent:
    settings = get_settings()
    return Agent(
        model=settings.bedrock_model_id,
        system_prompt=VERIFIER_SYSTEM_PROMPT,
        tools=[verify_health_status],
    )


@tool
def verifier_tool(resource_id: str, remediation_action: str) -> str:
    """Verify that a remediation action restored service health.

    Args:
        resource_id: The AWS resource to verify.
        remediation_action: The remediation that was applied.

    Returns:
        JSON with health status, individual checks, metrics, and summary.
    """
    logger.info("Verifier checking health for %s after %s", resource_id, remediation_action)

    try:
        agent = create_verifier()
        prompt = (
            f"Verify the health of resource '{resource_id}' after "
            f"remediation action '{remediation_action}' was applied.\n\n"
            f"Use the verify_health_status tool to check all health indicators."
        )
        response = agent(prompt)
        return str(response)
    except Exception as exc:
        logger.error("Verifier agent failed: %s", exc)
        # Direct tool call fallback
        result_str = verify_health_status(resource_id=resource_id)
        return result_str
