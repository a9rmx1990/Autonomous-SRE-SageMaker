"""Pydantic models for incidents, events, agents, and system state."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ── Enums ────────────────────────────────────────────────────────────────────

class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    ROOT_CAUSE_FOUND = "root_cause_found"
    REMEDIATING = "remediating"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    FAILED = "failed"


class EventType(str, Enum):
    SYSTEM = "system"
    ORCHESTRATOR = "orchestrator"
    LOG_ANALYST = "log_analyst"
    REMEDIATOR = "remediator"
    VERIFIER = "verifier"
    MEMORY = "memory"
    ERROR = "error"


# ── Core Models ──────────────────────────────────────────────────────────────

class IncidentEvent(BaseModel):
    """A single event in the incident lifecycle."""
    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)
    event_type: EventType
    agent: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None


class AgentFinding(BaseModel):
    """Structured output from the Log Analyst agent."""
    probable_root_cause: str
    supporting_evidence: list[str]
    affected_resources: list[str]
    severity: IncidentSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: str
    raw_metrics: dict[str, Any] = Field(default_factory=dict)


class RemediationAction(BaseModel):
    """A proposed remediation action."""
    id: str = Field(default_factory=_new_id)
    resource_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str
    risk: str = "low"
    current_state: dict[str, Any] = Field(default_factory=dict)
    proposed_state: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False
    executed: bool = False
    execution_result: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


class RemediationApproval(BaseModel):
    """Approval or rejection of a proposed remediation."""
    approved: bool
    approver: str = "system"
    reason: str = ""


class VerificationResult(BaseModel):
    """Result of post-remediation health verification."""
    healthy: bool
    checks: list[dict[str, Any]]
    metrics: dict[str, Any] = Field(default_factory=dict)
    verification_summary: str
    timestamp: datetime = Field(default_factory=_utcnow)


class IncidentCreate(BaseModel):
    """Payload to create a new incident."""
    service: str
    title: str
    description: str
    severity: IncidentSeverity = IncidentSeverity.HIGH
    source: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    """Full incident record."""
    id: str = Field(default_factory=_new_id)
    service: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.DETECTED
    source: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    duration_seconds: float | None = None
    events: list[IncidentEvent] = Field(default_factory=list)
    findings: AgentFinding | None = None
    remediation: RemediationAction | None = None
    verification: VerificationResult | None = None
    post_mortem: dict[str, Any] | None = None
    trace_id: str | None = None
    simulation: bool = False

    def add_event(
        self,
        event_type: EventType,
        agent: str,
        message: str,
        data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> IncidentEvent:
        event = IncidentEvent(
            event_type=event_type,
            agent=agent,
            message=message,
            data=data or {},
            duration_ms=duration_ms,
        )
        self.events.append(event)
        self.updated_at = _utcnow()
        return event


# ── System / Dashboard Models ────────────────────────────────────────────────

class TraceSpan(BaseModel):
    """An observability span in the agent execution trace."""
    span_id: str = Field(default_factory=_new_id)
    parent_id: str | None = None
    operation: str
    agent: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    """An entry in AgentCore Memory."""
    id: str = Field(default_factory=_new_id)
    incident_id: str
    category: str
    content: dict[str, Any]
    timestamp: datetime = Field(default_factory=_utcnow)
    tags: list[str] = Field(default_factory=list)


class ServiceStatus(BaseModel):
    """Health status of a monitored service."""
    name: str
    status: str = "healthy"
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    error_rate: float = 0.0
    latency_ms: float = 0.0
    instance_count: int = 1
    last_check: datetime = Field(default_factory=_utcnow)


class SystemHealth(BaseModel):
    """Overall system health dashboard data."""
    status: str = "healthy"
    services: list[ServiceStatus] = Field(default_factory=list)
    active_incidents: int = 0
    resolved_incidents: int = 0
    total_remediations: int = 0
    uptime_percent: float = 99.9
