"""Tests for core platform components.

All tests run in simulation mode without requiring AWS credentials.
"""

import json
import os
import pytest
import pytest_asyncio

# Force simulation mode
os.environ["SIMULATION_MODE"] = "true"
os.environ["BEDROCK_MODEL_ID"] = "us.anthropic.claude-sonnet-4-20250514"

from app.simulation.payment_incident import PaymentIncidentSimulator, SimulatedMetrics
from app.tools.remediation import ALLOWED_ACTIONS
from app.models import (
    Incident, IncidentCreate, IncidentSeverity, IncidentStatus,
    RemediationAction, VerificationResult, AgentFinding,
)


# ── Simulation Tests ─────────────────────────────────────────────────────────

class TestPaymentIncidentSimulator:
    def test_initial_state(self):
        sim = PaymentIncidentSimulator()
        assert sim.stage == "pre_incident"
        m = sim.current_metrics()
        assert m.healthy is True
        assert m.cpu_percent < 50

    def test_trigger_incident(self):
        sim = PaymentIncidentSimulator()
        alarm = sim.trigger_incident()
        assert sim.stage == "incident"
        assert alarm["source"] == "cloudwatch"
        assert alarm["simulation"] is True

        m = sim.current_metrics()
        assert m.healthy is False
        assert m.cpu_percent > 85
        assert m.alarm_state == "ALARM"

    def test_apply_remediation_scale_up(self):
        sim = PaymentIncidentSimulator()
        sim.trigger_incident()
        result = sim.apply_remediation("scale_up", {"desired_count": 4})
        assert result["success"] is True
        assert sim.stage == "post_scale"

        m = sim.current_metrics()
        assert m.desired_count == 4
        assert m.cpu_percent < 80

    def test_recovery(self):
        sim = PaymentIncidentSimulator()
        sim.trigger_incident()
        sim.apply_remediation("scale_up", {"desired_count": 4})
        sim.mark_recovered()
        assert sim.stage == "recovered"
        m = sim.current_metrics()
        assert m.healthy is True

    def test_cloudwatch_logs_incident(self):
        sim = PaymentIncidentSimulator()
        sim.trigger_incident()
        logs = sim.cloudwatch_logs()
        assert len(logs) > 3
        assert any("ERROR" == log["level"] for log in logs)
        assert all(log["simulation"] is True for log in logs)

    def test_cloudwatch_alarms(self):
        sim = PaymentIncidentSimulator()
        sim.trigger_incident()
        alarms = sim.cloudwatch_alarms()
        assert len(alarms) == 2
        assert any(a["state"] == "ALARM" for a in alarms)


# ── Remediation Allowlist Tests ──────────────────────────────────────────────

class TestRemediationAllowlist:
    def test_allowed_actions_exist(self):
        expected = {"restart_service", "scale_up", "flush_cache", "restart_container", "clear_stuck_queue"}
        assert set(ALLOWED_ACTIONS.keys()) == expected

    def test_all_actions_callable(self):
        for name, fn in ALLOWED_ACTIONS.items():
            assert callable(fn), f"{name} is not callable"

    def test_disallowed_action_rejected(self):
        from app.tools.remediation import execute_remediation
        result = json.loads(execute_remediation(
            resource_id="test/resource",
            action="rm_rf_slash",
            parameters="{}",
        ))
        assert result["success"] is False
        assert "not in the approved" in result["error"]


# ── Model Tests ──────────────────────────────────────────────────────────────

class TestModels:
    def test_incident_create(self):
        data = IncidentCreate(
            service="test-service",
            title="Test incident",
            description="Testing",
            severity=IncidentSeverity.HIGH,
        )
        assert data.service == "test-service"

    def test_incident_add_event(self):
        from app.models import EventType
        incident = Incident(
            service="test", title="test", description="test",
            severity=IncidentSeverity.LOW,
        )
        event = incident.add_event(EventType.SYSTEM, "system", "hello")
        assert len(incident.events) == 1
        assert event.message == "hello"

    def test_remediation_action_validation(self):
        action = RemediationAction(
            resource_id="test/res",
            action="scale_up",
            reason="test",
        )
        assert action.approved is False
        assert action.executed is False

    def test_verification_result(self):
        v = VerificationResult(
            healthy=True,
            checks=[{"name": "CPU", "status": "pass"}],
            verification_summary="All good",
        )
        assert v.healthy is True


# ── Simulation Tool Tests ────────────────────────────────────────────────────

class TestSimulationTools:
    def test_fetch_alarms_simulation(self):
        from app.tools.cloudwatch import fetch_cloudwatch_alarms, reset_simulator
        reset_simulator()
        result = json.loads(fetch_cloudwatch_alarms(service_name="payment-api"))
        assert result["simulation"] is True
        assert "alarms" in result

    def test_verify_health_simulation(self):
        from app.tools.verification import verify_health_status
        from app.tools.cloudwatch import reset_simulator
        sim = reset_simulator()
        sim.trigger_incident()
        sim.apply_remediation("scale_up", {"desired_count": 4})

        result = json.loads(verify_health_status(
            resource_id="ecs-service/prod-ecs-cluster/payment-api"
        ))
        assert result["simulation"] is True
        assert "checks" in result
        assert "healthy" in result


# ── Memory Tests ─────────────────────────────────────────────────────────────

class TestMemory:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        from app.memory.hooks import MemoryManager
        mem = MemoryManager()

        entry = await mem.store_incident(
            incident_id="test-123",
            service="payment-api",
            summary="Test incident",
            root_cause="CPU spike",
            remediation="scale_up",
            verification_result="healthy",
        )
        assert entry.incident_id == "test-123"

        results = await mem.retrieve_context("payment-api", "CPU spike")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_memory_fallback(self):
        from app.memory.hooks import MemoryManager
        mem = MemoryManager()
        # Should work without AgentCore
        assert mem._agentcore_client is None
        entries = mem.get_all_entries()
        assert isinstance(entries, list)
