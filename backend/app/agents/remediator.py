"""Remediator: specialist agent for safe infrastructure remediation.

Never allows arbitrary commands. Maps LLM decisions to an explicit
allowlist of approved actions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import Agent, tool

from ..config import get_settings
from ..tools.remediation import execute_remediation, ALLOWED_ACTIONS

logger = logging.getLogger(__name__)

REMEDIATOR_SYSTEM_PROMPT = """\
You are Remediator, a specialist SRE agent responsible for proposing
and executing safe infrastructure remediations.

SAFETY RULES:
1. You may ONLY propose actions from this approved list:
   {allowed_actions}
2. Never suggest arbitrary shell commands or raw AWS CLI commands.
3. Always explain your reasoning and the expected outcome.
4. Assess risk level: low, medium, or high.
5. In simulation mode, actions are safe to execute automatically.

Return your proposal as a JSON object:
- action: one of the approved actions
- resource_id: the AWS resource to remediate
- parameters: action-specific parameters (as a dict)
- reason: why this action is appropriate
- risk: "low", "medium", or "high"
- current_state: relevant current values
- proposed_state: expected values after remediation
""".format(allowed_actions=list(ALLOWED_ACTIONS.keys()))


def create_remediator() -> Agent:
    settings = get_settings()
    return Agent(
        model=settings.bedrock_model_id,
        system_prompt=REMEDIATOR_SYSTEM_PROMPT,
        tools=[execute_remediation],
    )


@tool
def remediator_tool(
    service_name: str,
    root_cause: str,
    evidence: str,
    resource_id: str,
) -> str:
    """Propose and execute a safe remediation for an infrastructure incident.

    Args:
        service_name: Name of the affected service.
        root_cause: The identified root cause from investigation.
        evidence: Supporting evidence from the log analysis.
        resource_id: The AWS resource identifier to remediate.

    Returns:
        JSON with the proposed action, execution result, and safety details.
    """
    settings = get_settings()
    logger.info("Remediator evaluating action for %s", service_name)

    try:
        agent = create_remediator()
        prompt = (
            f"Service '{service_name}' is experiencing an incident.\n\n"
            f"Root cause: {root_cause}\n"
            f"Evidence: {evidence}\n"
            f"Resource: {resource_id}\n\n"
            f"Simulation mode: {settings.simulation_mode}\n\n"
            f"Propose and execute the safest remediation action."
        )
        response = agent(prompt)
        return str(response)
    except Exception as exc:
        logger.error("Remediator agent failed: %s", exc)
        # Deterministic fallback for simulation
        if settings.simulation_mode:
            from ..tools.cloudwatch import get_simulator
            sim = get_simulator()

            # Execute the scale_up action directly
            result = sim.apply_remediation("scale_up", {"desired_count": 4})
            fallback = {
                "action": "scale_up",
                "resource_id": resource_id,
                "parameters": {"desired_count": 4},
                "reason": (
                    f"Root cause is CPU saturation with container crash loop. "
                    f"Scaling from 2 to 4 tasks distributes load and restores availability."
                ),
                "risk": "low",
                "current_state": {"desired_count": 2, "running_count": 1},
                "proposed_state": {"desired_count": 4},
                "execution_result": result,
                "simulation": True,
                "note": "Remediation applied via simulation fallback (Bedrock agent unavailable)",
            }
            return json.dumps(fallback, indent=2)
        return json.dumps({"error": str(exc), "action": "none", "success": False})
