"""FastAPI routes for the Autonomous SRE control plane.

Provides REST endpoints for incident management and SSE for live updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..agents.orchestrator import get_orchestrator
from ..config import get_settings
from ..models import (
    Incident,
    IncidentCreate,
    IncidentSeverity,
    IncidentStatus,
    RemediationApproval,
    SystemHealth,
    ServiceStatus,
    MemoryEntry,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "version": settings.version,
        "simulation_mode": settings.simulation_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── System Dashboard ────────────────────────────────────────────────────────

@router.get("/api/dashboard")
async def get_dashboard():
    orch = get_orchestrator()
    incidents = orch.list_incidents()
    active = [i for i in incidents if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)]
    resolved = [i for i in incidents if i.status == IncidentStatus.RESOLVED]
    settings = get_settings()

    services = [
        ServiceStatus(name="payment-api", status="healthy", cpu_percent=24.3, memory_percent=48.1,
                       error_rate=0.1, latency_ms=62, instance_count=2),
        ServiceStatus(name="auth-service", status="healthy", cpu_percent=18.7, memory_percent=35.2,
                       error_rate=0.0, latency_ms=45, instance_count=3),
        ServiceStatus(name="order-service", status="healthy", cpu_percent=31.5, memory_percent=52.8,
                       error_rate=0.2, latency_ms=78, instance_count=2),
        ServiceStatus(name="notification-service", status="healthy", cpu_percent=12.1, memory_percent=28.4,
                       error_rate=0.0, latency_ms=35, instance_count=1),
    ]

    # Update service status based on active incidents
    for svc in services:
        for inc in active:
            if inc.service == svc.name:
                svc.status = "degraded" if inc.severity in (IncidentSeverity.CRITICAL, IncidentSeverity.HIGH) else "warning"

    system_status = "healthy"
    if any(s.status == "degraded" for s in services):
        system_status = "degraded"
    elif any(s.status == "warning" for s in services):
        system_status = "investigating"

    return SystemHealth(
        status=system_status,
        services=services,
        active_incidents=len(active),
        resolved_incidents=len(resolved),
        total_remediations=sum(1 for i in incidents if i.remediation and i.remediation.executed),
        uptime_percent=99.9 if not active else 98.5,
    )


# ── Incidents ────────────────────────────────────────────────────────────────

@router.get("/api/incidents")
async def list_incidents():
    orch = get_orchestrator()
    return orch.list_incidents()


@router.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    orch = get_orchestrator()
    incident = orch.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/api/incidents")
async def create_incident(data: IncidentCreate):
    orch = get_orchestrator()
    incident = orch.create_incident(data)
    return incident


@router.post("/api/incidents/{incident_id}/run")
async def run_incident(incident_id: str, background_tasks: BackgroundTasks):
    orch = get_orchestrator()
    incident = orch.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status not in (IncidentStatus.DETECTED, IncidentStatus.FAILED):
        raise HTTPException(status_code=400, detail=f"Incident is already {incident.status.value}")

    background_tasks.add_task(orch.run_incident, incident_id)
    return {"message": "Incident investigation started", "incident_id": incident_id}


@router.post("/api/incidents/{incident_id}/approve-remediation")
async def approve_remediation(incident_id: str, approval: RemediationApproval):
    orch = get_orchestrator()
    incident = orch.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not incident.remediation:
        raise HTTPException(status_code=400, detail="No remediation proposed")
    incident.remediation.approved = approval.approved
    return {"approved": approval.approved, "incident_id": incident_id}


# ── SSE Events ───────────────────────────────────────────────────────────────

@router.get("/api/incidents/{incident_id}/events")
async def stream_events(incident_id: str):
    orch = get_orchestrator()
    incident = orch.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    async def event_generator():
        # First, send all existing events
        for event in incident.events:
            data = json.dumps(event.model_dump(), default=str)
            yield f"data: {data}\n\n"

        # Then stream new events
        async for event in orch.event_stream(incident_id):
            if event.message == "keepalive":
                yield f": keepalive\n\n"
            else:
                data = json.dumps(event.model_dump(), default=str)
                yield f"data: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Trace ────────────────────────────────────────────────────────────────────

@router.get("/api/incidents/{incident_id}/trace")
async def get_trace(incident_id: str):
    orch = get_orchestrator()
    incident = orch.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "incident_id": incident_id,
        "trace_id": incident.trace_id,
        "events": [e.model_dump() for e in incident.events],
        "status": incident.status.value,
    }


# ── Memory ───────────────────────────────────────────────────────────────────

@router.get("/api/memory")
async def get_memory():
    orch = get_orchestrator()
    entries = orch.memory.get_all_entries()
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


@router.get("/api/memory/{service}")
async def get_memory_for_service(service: str):
    orch = get_orchestrator()
    entries = orch.memory.get_entries_for_service(service)
    return {"entries": [e.model_dump() for e in entries], "count": len(entries)}


# ── Simulation ───────────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    scenario: str = "payment_cpu_spike"


@router.post("/api/simulate")
async def simulate_incident(req: SimulateRequest, background_tasks: BackgroundTasks):
    """Create and auto-run a simulated incident."""
    settings = get_settings()
    if not settings.simulation_mode:
        raise HTTPException(status_code=400, detail="Simulation mode is not enabled")

    orch = get_orchestrator()

    if req.scenario == "payment_cpu_spike":
        data = IncidentCreate(
            service="payment-api",
            title="Payment API CPU Spike & Container Crash",
            description=(
                "CPU utilization for ECS service payment-api exceeded 95%. "
                "Repeated container crashes detected (OOMKilled). "
                "HTTP 5xx error rate spiked to 18%. "
                "CloudWatch alarm 'payment-api-cpu-high' is in ALARM state. "
                "Latency p99 increased from 65ms to 4200ms."
            ),
            severity=IncidentSeverity.CRITICAL,
            source="cloudwatch_alarm",
            metadata={
                "alarm_name": "payment-api-cpu-high",
                "cluster": "prod-ecs-cluster",
                "region": settings.aws_region,
            },
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    incident = orch.create_incident(data)
    background_tasks.add_task(orch.run_incident, incident.id)

    return {"incident_id": incident.id, "message": "Simulation started", "scenario": req.scenario}
