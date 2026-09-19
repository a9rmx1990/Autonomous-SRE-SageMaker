"""Simulated Payment API CPU spike + container crash scenario.

Generates realistic CloudWatch-style metrics, logs, and alarm states
without touching real AWS infrastructure.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


@dataclass
class SimulatedMetrics:
    """A snapshot of simulated service metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    http_5xx_rate: float = 0.0
    http_2xx_rate: float = 0.0
    latency_p99_ms: float = 0.0
    container_restarts: int = 0
    desired_count: int = 2
    running_count: int = 2
    alarm_state: str = "OK"
    healthy: bool = True


class PaymentIncidentSimulator:
    """Drives the full lifecycle of the simulated payment-api incident.

    Stages:
        pre_incident   -> normal metrics
        incident       -> degraded metrics (CPU spike, crashes, 5xx)
        post_scale     -> recovering after scale-up
        recovered      -> healthy metrics
    """

    SERVICE_NAME = "payment-api"
    CLUSTER = "prod-ecs-cluster"
    LOG_GROUP = "/ecs/payment-api"

    def __init__(self) -> None:
        self._stage = "pre_incident"
        self._remediation_applied: str | None = None
        self._scale_target: int = 2

    # ── Stage transitions ────────────────────────────────────────────────

    def trigger_incident(self) -> dict[str, Any]:
        """Move to incident stage and return the alarm payload."""
        self._stage = "incident"
        return self._alarm_payload()

    def apply_remediation(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._remediation_applied = action
        if action == "scale_up":
            self._scale_target = (params or {}).get("desired_count", 4)
        self._stage = "post_scale"
        return {
            "action": action,
            "success": True,
            "message": f"Remediation '{action}' applied in SIMULATION mode.",
            "simulation": True,
        }

    def mark_recovered(self) -> None:
        self._stage = "recovered"

    @property
    def stage(self) -> str:
        return self._stage

    # ── Metric generators ────────────────────────────────────────────────

    def current_metrics(self) -> SimulatedMetrics:
        if self._stage == "pre_incident":
            return SimulatedMetrics(
                cpu_percent=round(random.uniform(18, 32), 1),
                memory_percent=round(random.uniform(40, 55), 1),
                http_5xx_rate=round(random.uniform(0.0, 0.2), 2),
                http_2xx_rate=round(random.uniform(98.5, 99.8), 1),
                latency_p99_ms=round(random.uniform(45, 85), 0),
                container_restarts=0,
                desired_count=2,
                running_count=2,
                alarm_state="OK",
                healthy=True,
            )
        elif self._stage == "incident":
            return SimulatedMetrics(
                cpu_percent=round(random.uniform(92, 99), 1),
                memory_percent=round(random.uniform(78, 92), 1),
                http_5xx_rate=round(random.uniform(12, 28), 1),
                http_2xx_rate=round(random.uniform(70, 85), 1),
                latency_p99_ms=round(random.uniform(2800, 5200), 0),
                container_restarts=random.randint(4, 9),
                desired_count=2,
                running_count=random.choice([0, 1, 1]),
                alarm_state="ALARM",
                healthy=False,
            )
        elif self._stage == "post_scale":
            return SimulatedMetrics(
                cpu_percent=round(random.uniform(38, 52), 1),
                memory_percent=round(random.uniform(45, 60), 1),
                http_5xx_rate=round(random.uniform(0.1, 1.5), 2),
                http_2xx_rate=round(random.uniform(97, 99.5), 1),
                latency_p99_ms=round(random.uniform(60, 140), 0),
                container_restarts=0,
                desired_count=self._scale_target,
                running_count=self._scale_target,
                alarm_state="OK",
                healthy=True,
            )
        else:  # recovered
            return SimulatedMetrics(
                cpu_percent=round(random.uniform(20, 35), 1),
                memory_percent=round(random.uniform(40, 52), 1),
                http_5xx_rate=round(random.uniform(0.0, 0.3), 2),
                http_2xx_rate=round(random.uniform(99.0, 99.9), 1),
                latency_p99_ms=round(random.uniform(42, 75), 0),
                container_restarts=0,
                desired_count=self._scale_target,
                running_count=self._scale_target,
                alarm_state="OK",
                healthy=True,
            )

    def cloudwatch_logs(self) -> list[dict[str, Any]]:
        """Return simulated CloudWatch log entries."""
        now = datetime.now(timezone.utc)
        base: list[dict[str, Any]] = []

        if self._stage == "incident":
            base = [
                {"timestamp": (now - timedelta(minutes=4)).isoformat(), "level": "ERROR",
                 "message": "Container health check failed: connection refused on port 8080",
                 "source": "ecs-agent"},
                {"timestamp": (now - timedelta(minutes=3, seconds=45)).isoformat(), "level": "WARN",
                 "message": "CPU utilization at 96.2% for task arn:aws:ecs:us-east-1:123456789:task/payment-api/a1b2c3",
                 "source": "cloudwatch-metrics"},
                {"timestamp": (now - timedelta(minutes=3, seconds=30)).isoformat(), "level": "ERROR",
                 "message": "OOMKilled: container exceeded memory limit (512Mi). PID 1 terminated.",
                 "source": "ecs-agent"},
                {"timestamp": (now - timedelta(minutes=3)).isoformat(), "level": "ERROR",
                 "message": "java.lang.OutOfMemoryError: Java heap space\n  at com.payment.api.TransactionProcessor.process(TransactionProcessor.java:142)",
                 "source": "application"},
                {"timestamp": (now - timedelta(minutes=2, seconds=30)).isoformat(), "level": "ERROR",
                 "message": "HTTP 503 Service Unavailable: upstream connect error or disconnect/reset before headers. retries exhausted",
                 "source": "alb"},
                {"timestamp": (now - timedelta(minutes=2)).isoformat(), "level": "WARN",
                 "message": "ECS service payment-api has 5 container restarts in the last 10 minutes (restart loop detected)",
                 "source": "ecs-service"},
                {"timestamp": (now - timedelta(minutes=1, seconds=30)).isoformat(), "level": "ERROR",
                 "message": "CloudWatch Alarm 'payment-api-cpu-high' transitioned from OK to ALARM. Threshold: CPUUtilization > 90% for 2 consecutive periods.",
                 "source": "cloudwatch-alarm"},
                {"timestamp": (now - timedelta(minutes=1)).isoformat(), "level": "ERROR",
                 "message": "Latency p99 spike: 4200ms (baseline: 65ms). SLO breach detected for payment-api.",
                 "source": "cloudwatch-metrics"},
            ]
        elif self._stage in ("post_scale", "recovered"):
            base = [
                {"timestamp": (now - timedelta(seconds=30)).isoformat(), "level": "INFO",
                 "message": f"ECS service payment-api scaled to {self._scale_target} tasks. All tasks healthy.",
                 "source": "ecs-service"},
                {"timestamp": (now - timedelta(seconds=15)).isoformat(), "level": "INFO",
                 "message": "Health check passed: HTTP 200 on /health. Latency: 52ms.",
                 "source": "alb"},
                {"timestamp": now.isoformat(), "level": "INFO",
                 "message": "CloudWatch Alarm 'payment-api-cpu-high' transitioned from ALARM to OK.",
                 "source": "cloudwatch-alarm"},
            ]
        else:
            base = [
                {"timestamp": now.isoformat(), "level": "INFO",
                 "message": "Service payment-api operating normally. CPU: 24%, Memory: 48%, p99: 62ms.",
                 "source": "cloudwatch-metrics"},
            ]

        for entry in base:
            entry["log_group"] = self.LOG_GROUP
            entry["service"] = self.SERVICE_NAME
            entry["simulation"] = True

        return base

    def cloudwatch_alarms(self) -> list[dict[str, Any]]:
        m = self.current_metrics()
        return [
            {
                "alarm_name": "payment-api-cpu-high",
                "metric": "CPUUtilization",
                "threshold": 90.0,
                "current_value": m.cpu_percent,
                "state": m.alarm_state,
                "service": self.SERVICE_NAME,
                "simulation": True,
            },
            {
                "alarm_name": "payment-api-5xx-high",
                "metric": "HTTPCode_Target_5XX_Count",
                "threshold": 5.0,
                "current_value": m.http_5xx_rate,
                "state": "ALARM" if m.http_5xx_rate > 5 else "OK",
                "service": self.SERVICE_NAME,
                "simulation": True,
            },
        ]

    def resource_health(self) -> dict[str, Any]:
        m = self.current_metrics()
        return {
            "resource_id": f"ecs-service/{self.CLUSTER}/{self.SERVICE_NAME}",
            "resource_type": "ECS Service",
            "service": self.SERVICE_NAME,
            "cluster": self.CLUSTER,
            "cpu_percent": m.cpu_percent,
            "memory_percent": m.memory_percent,
            "desired_count": m.desired_count,
            "running_count": m.running_count,
            "container_restarts": m.container_restarts,
            "http_5xx_rate": m.http_5xx_rate,
            "latency_p99_ms": m.latency_p99_ms,
            "alarm_state": m.alarm_state,
            "healthy": m.healthy,
            "simulation": True,
        }

    # ── Private ──────────────────────────────────────────────────────────

    def _alarm_payload(self) -> dict[str, Any]:
        return {
            "source": "cloudwatch",
            "alarm_name": "payment-api-cpu-high",
            "service": self.SERVICE_NAME,
            "description": (
                "CPU utilization for ECS service payment-api exceeded 95% "
                "with repeated container crashes and HTTP 5xx spike."
            ),
            "severity": "critical",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "cpu_percent": 96.2,
                "memory_percent": 88.4,
                "http_5xx_rate": 18.7,
                "container_restarts": 6,
                "latency_p99_ms": 4200,
            },
            "simulation": True,
        }
