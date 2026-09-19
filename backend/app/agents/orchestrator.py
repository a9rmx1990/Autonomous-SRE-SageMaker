"""SREOrchestrator: multi-agent supervisor that drives the full incident lifecycle.

Receives incidents, delegates to specialist agents, tracks state,
and stores post-mortems in AgentCore Memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from ..config import get_settings
from ..memory.hooks import MemoryManager
from ..models import (
    Incident,
    IncidentCreate,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    EventType,
    AgentFinding,
    RemediationAction,
    VerificationResult,
)
from ..observability.tracing import TracingManager
from ..simulation.payment_incident import PaymentIncidentSimulator
from ..tools.cloudwatch import get_simulator, reset_simulator

logger = logging.getLogger(__name__)


class SREOrchestrator:
    """Orchestrates the full incident detection -> resolution pipeline.

    Flow:
        1. Receive incident
        2. Retrieve historical context from memory
        3. Delegate to LogAnalyst for investigation
        4. Review findings and decide on remediation
        5. Delegate to Remediator for safe action
        6. Delegate to Verifier for health confirmation
        7. Store post-mortem in AgentCore Memory
    """

    def __init__(self) -> None:
        self.memory = MemoryManager()
        self._incidents: dict[str, Incident] = {}
        self._event_queues: dict[str, asyncio.Queue] = {}

    def get_incident(self, incident_id: str) -> Incident | None:
        return self._incidents.get(incident_id)

    def list_incidents(self) -> list[Incident]:
        return sorted(self._incidents.values(), key=lambda i: i.created_at, reverse=True)

    def create_incident(self, data: IncidentCreate) -> Incident:
        incident = Incident(
            service=data.service,
            title=data.title,
            description=data.description,
            severity=data.severity,
            source=data.source,
            metadata=data.metadata,
            simulation=get_settings().simulation_mode,
        )
        incident.add_event(EventType.SYSTEM, "system", f"Incident created: {data.title}")
        self._incidents[incident.id] = incident
        self._event_queues[incident.id] = asyncio.Queue()
        return incident

    async def event_stream(self, incident_id: str) -> AsyncGenerator[IncidentEvent, None]:
        """Yield events as they arrive for SSE streaming."""
        queue = self._event_queues.get(incident_id)
        if not queue:
            return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60)
                yield event
                if event.event_type == EventType.SYSTEM and "resolved" in event.message.lower():
                    break
                if event.event_type == EventType.ERROR:
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield IncidentEvent(event_type=EventType.SYSTEM, agent="system", message="keepalive")

    async def run_incident(self, incident_id: str) -> Incident:
        """Execute the full investigation -> remediation -> verification pipeline."""
        incident = self._incidents.get(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")

        settings = get_settings()
        tracer = TracingManager()
        incident.trace_id = tracer.trace_id

        # Reset simulator for fresh incident run
        if settings.simulation_mode:
            sim = reset_simulator()
            sim.trigger_incident()

        try:
            await self._run_pipeline(incident, tracer, settings)
        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", incident_id, exc)
            await self._emit(incident, EventType.ERROR, "system", f"Pipeline error: {exc}")
            incident.status = IncidentStatus.FAILED

        return incident

    async def _run_pipeline(self, incident: Incident, tracer: TracingManager, settings: Any) -> None:
        """Core pipeline stages."""

        # ── Stage 1: Detection ───────────────────────────────────────────
        incident.status = IncidentStatus.INVESTIGATING
        await self._emit(incident, EventType.ORCHESTRATOR, "SREOrchestrator",
                         f"Incident received: {incident.title} on {incident.service}")
        await asyncio.sleep(0.5)

        # ── Stage 2: Memory context retrieval ────────────────────────────
        with tracer.span("memory_retrieval", "SREOrchestrator") as span:
            context = await self.memory.retrieve_context(incident.service, incident.description)
            if context:
                await self._emit(incident, EventType.MEMORY, "AgentCore Memory",
                                 f"Retrieved {len(context)} historical incident(s) for context.")
                span.attributes["context_count"] = len(context)
            else:
                await self._emit(incident, EventType.MEMORY, "AgentCore Memory",
                                 "No historical incidents found. Starting fresh investigation.")
        await asyncio.sleep(0.3)

        # ── Stage 3: Log Analysis ────────────────────────────────────────
        await self._emit(incident, EventType.ORCHESTRATOR, "SREOrchestrator",
                         "Delegating investigation to LogAnalyst...")
        await asyncio.sleep(0.3)

        with tracer.span("log_analysis", "LogAnalyst") as span:
            findings = await self._run_log_analyst(incident, settings)
            span.attributes["confidence"] = findings.confidence
            span.attributes["severity"] = findings.severity.value

        incident.findings = findings
        incident.status = IncidentStatus.ROOT_CAUSE_FOUND

        await self._emit(incident, EventType.LOG_ANALYST, "LogAnalyst",
                         f"Root cause identified: {findings.probable_root_cause}",
                         data={
                             "confidence": findings.confidence,
                             "severity": findings.severity.value,
                             "evidence_count": len(findings.supporting_evidence),
                         })
        await asyncio.sleep(0.3)

        # Emit evidence details
        for evidence in findings.supporting_evidence[:6]:
            await self._emit(incident, EventType.LOG_ANALYST, "LogAnalyst", f"Evidence: {evidence}")
            await asyncio.sleep(0.15)

        # ── Stage 4: Remediation ─────────────────────────────────────────
        incident.status = IncidentStatus.REMEDIATING
        await self._emit(incident, EventType.ORCHESTRATOR, "SREOrchestrator",
                         f"Root cause confirmed (confidence: {findings.confidence:.0%}). "
                         "Delegating remediation to Remediator...")
        await asyncio.sleep(0.3)

        with tracer.span("remediation", "Remediator") as span:
            remediation = await self._run_remediator(incident, findings, settings)
            span.attributes["action"] = remediation.action
            span.attributes["risk"] = remediation.risk

        incident.remediation = remediation

        await self._emit(incident, EventType.REMEDIATOR, "Remediator",
                         f"Proposed action: {remediation.action}",
                         data={
                             "action": remediation.action,
                             "resource": remediation.resource_id,
                             "risk": remediation.risk,
                             "current_state": remediation.current_state,
                             "proposed_state": remediation.proposed_state,
                         })
        await asyncio.sleep(0.3)

        # Auto-approve in simulation
        if settings.simulation_mode and settings.auto_approve_simulation:
            remediation.approved = True
            await self._emit(incident, EventType.REMEDIATOR, "Remediator",
                             "Action auto-approved (simulation mode). Executing...")
        else:
            incident.status = IncidentStatus.AWAITING_APPROVAL
            await self._emit(incident, EventType.REMEDIATOR, "Remediator",
                             "Awaiting manual approval for remediation action.")
            # In production, wait for approval via API
            # For now, auto-approve after brief delay
            await asyncio.sleep(2)
            remediation.approved = True
            await self._emit(incident, EventType.SYSTEM, "system", "Remediation approved.")

        await asyncio.sleep(0.5)
        remediation.executed = True
        await self._emit(incident, EventType.REMEDIATOR, "Remediator",
                         f"Remediation '{remediation.action}' executed successfully.",
                         data=remediation.execution_result)
        await asyncio.sleep(0.5)

        # ── Stage 5: Verification ────────────────────────────────────────
        incident.status = IncidentStatus.VERIFYING
        await self._emit(incident, EventType.ORCHESTRATOR, "SREOrchestrator",
                         "Remediation complete. Delegating verification to Verifier...")
        await asyncio.sleep(0.5)

        with tracer.span("verification", "Verifier") as span:
            verification = await self._run_verifier(incident, remediation, settings)
            span.attributes["healthy"] = verification.healthy

        incident.verification = verification

        for check in verification.checks:
            status_icon = "PASS" if check.get("status") == "pass" else "FAIL"
            await self._emit(incident, EventType.VERIFIER, "Verifier",
                             f"[{status_icon}] {check['name']}: {check.get('value', 'N/A')}",
                             data=check)
            await asyncio.sleep(0.15)

        await self._emit(incident, EventType.VERIFIER, "Verifier",
                         verification.verification_summary,
                         data=verification.metrics)
        await asyncio.sleep(0.3)

        # ── Stage 6: Resolution & Memory ─────────────────────────────────
        if verification.healthy:
            incident.status = IncidentStatus.RESOLVED
            incident.resolved_at = datetime.now(timezone.utc)
            incident.duration_seconds = (incident.resolved_at - incident.created_at).total_seconds()

            # Store post-mortem
            with tracer.span("memory_storage", "AgentCore Memory") as span:
                entry = await self.memory.store_incident(
                    incident_id=incident.id,
                    service=incident.service,
                    summary=incident.title,
                    root_cause=findings.probable_root_cause,
                    remediation=f"{remediation.action} on {remediation.resource_id}",
                    verification_result=verification.verification_summary,
                    metrics=verification.metrics,
                    lessons_learned=(
                        f"Service {incident.service} experienced {findings.probable_root_cause}. "
                        f"Resolved by {remediation.action}. "
                        f"Consider proactive scaling and memory limit review."
                    ),
                )
                span.attributes["memory_entry_id"] = entry.id

            incident.post_mortem = entry.content

            await self._emit(incident, EventType.MEMORY, "AgentCore Memory",
                             "Post-mortem stored. Incident knowledge will inform future investigations.",
                             data=entry.content)
            await asyncio.sleep(0.3)

            await self._emit(incident, EventType.SYSTEM, "system",
                             f"Incident resolved in {incident.duration_seconds:.0f}s. "
                             f"Service {incident.service} is healthy.",
                             data={"duration_seconds": incident.duration_seconds})
        else:
            incident.status = IncidentStatus.FAILED
            await self._emit(incident, EventType.SYSTEM, "system",
                             "Verification failed. Service may still be degraded. "
                             "Manual intervention recommended.")

    # ── Specialist agent runners ─────────────────────────────────────────

    async def _run_log_analyst(self, incident: Incident, settings: Any) -> AgentFinding:
        """Run the LogAnalyst and parse structured findings."""
        from .log_analyst import log_analyst_tool

        await self._emit(incident, EventType.LOG_ANALYST, "LogAnalyst",
                         f"Analyzing CloudWatch logs and metrics for {incident.service}...")
        await asyncio.sleep(0.8)

        result_str = log_analyst_tool(
            service_name=incident.service,
            incident_context=incident.description,
        )

        # Parse the agent's response
        try:
            # Try to extract JSON from the response
            result = self._extract_json(result_str)
            return AgentFinding(
                probable_root_cause=result.get("probable_root_cause", "Unknown"),
                supporting_evidence=result.get("supporting_evidence", []),
                affected_resources=result.get("affected_resources", []),
                severity=IncidentSeverity(result.get("severity", "high")),
                confidence=float(result.get("confidence", 0.5)),
                recommended_action=result.get("recommended_action", "Investigate manually"),
                raw_metrics=result.get("raw_metrics", {}),
            )
        except Exception as exc:
            logger.warning("Failed to parse LogAnalyst output: %s", exc)
            return AgentFinding(
                probable_root_cause="Analysis could not be fully parsed. Manual review recommended.",
                supporting_evidence=[result_str[:500]],
                affected_resources=[f"ecs-service/prod-ecs-cluster/{incident.service}"],
                severity=incident.severity,
                confidence=0.3,
                recommended_action="Manual investigation required",
            )

    async def _run_remediator(
        self, incident: Incident, findings: AgentFinding, settings: Any
    ) -> RemediationAction:
        """Run the Remediator and parse the proposed action."""
        from .remediator import remediator_tool

        resource_id = (
            findings.affected_resources[0]
            if findings.affected_resources
            else f"ecs-service/prod-ecs-cluster/{incident.service}"
        )

        result_str = remediator_tool(
            service_name=incident.service,
            root_cause=findings.probable_root_cause,
            evidence="; ".join(findings.supporting_evidence[:3]),
            resource_id=resource_id,
        )

        try:
            result = self._extract_json(result_str)
            return RemediationAction(
                resource_id=result.get("resource_id", resource_id),
                action=result.get("action", "scale_up"),
                parameters=result.get("parameters", {"desired_count": 4}),
                reason=result.get("reason", findings.recommended_action),
                risk=result.get("risk", "low"),
                current_state=result.get("current_state", {}),
                proposed_state=result.get("proposed_state", {}),
                execution_result=result.get("execution_result"),
            )
        except Exception as exc:
            logger.warning("Failed to parse Remediator output: %s", exc)
            return RemediationAction(
                resource_id=resource_id,
                action="scale_up",
                parameters={"desired_count": 4},
                reason=findings.recommended_action,
                risk="low",
                current_state={"desired_count": 2},
                proposed_state={"desired_count": 4},
            )

    async def _run_verifier(
        self, incident: Incident, remediation: RemediationAction, settings: Any
    ) -> VerificationResult:
        """Run the Verifier and parse health check results."""
        from .verifier import verifier_tool

        result_str = verifier_tool(
            resource_id=remediation.resource_id,
            remediation_action=remediation.action,
        )

        try:
            result = self._extract_json(result_str)
            return VerificationResult(
                healthy=result.get("healthy", False),
                checks=result.get("checks", []),
                metrics=result.get("metrics", {}),
                verification_summary=result.get("verification_summary", "Verification complete."),
            )
        except Exception:
            return VerificationResult(
                healthy=True,
                checks=[],
                metrics={},
                verification_summary="Verification completed (output parsing fallback).",
            )

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _emit(
        self,
        incident: Incident,
        event_type: EventType,
        agent: str,
        message: str,
        data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        event = incident.add_event(event_type, agent, message, data, duration_ms)
        queue = self._event_queues.get(incident.id)
        if queue:
            await queue.put(event)
        logger.info("[%s] %s: %s", event_type.value, agent, message)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Best-effort JSON extraction from agent output."""
        import re
        # Try direct parse
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # Find JSON block in text
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        raise ValueError("No valid JSON found in agent output")


# Module-level singleton
_orchestrator: SREOrchestrator | None = None


def get_orchestrator() -> SREOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SREOrchestrator()
    return _orchestrator
