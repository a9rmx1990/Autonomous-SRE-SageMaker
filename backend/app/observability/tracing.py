"""OpenTelemetry instrumentation for agent execution tracing.

Captures spans for orchestrator decisions, specialist agent calls,
tool invocations, and remediation actions. Falls back gracefully
when OTEL collectors are unavailable.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator
from dataclasses import dataclass, field

from ..config import get_settings
from ..models import TraceSpan

logger = logging.getLogger(__name__)


def _new_span_id() -> str:
    import uuid
    return uuid.uuid4().hex[:16]


@dataclass
class SpanRecord:
    """In-memory span record for the trace visualization."""
    span_id: str
    parent_id: str | None
    operation: str
    agent: str
    start_time: float
    end_time: float | None = None
    status: str = "running"
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


class TracingManager:
    """Manages trace spans for an incident investigation lifecycle.

    Stores spans in memory for the dashboard trace view.
    Optionally exports to OpenTelemetry/X-Ray when configured.
    """

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or _new_span_id()
        self.spans: list[SpanRecord] = []
        self._otel_tracer = None
        self._init_otel()

    def _init_otel(self) -> None:
        settings = get_settings()
        if not settings.otel_enabled:
            return
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": "autonomous-sre"})
            provider = TracerProvider(resource=resource)

            if settings.xray_enabled:
                try:
                    from opentelemetry.sdk.trace.export import BatchSpanProcessor
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
                    provider.add_span_processor(BatchSpanProcessor(exporter))
                except ImportError:
                    logger.warning("OTLP exporter not installed; traces will be in-memory only.")

            trace.set_tracer_provider(provider)
            self._otel_tracer = trace.get_tracer("autonomous-sre")
        except Exception as exc:
            logger.warning("OpenTelemetry init failed (non-fatal): %s", exc)

    @contextmanager
    def span(
        self,
        operation: str,
        agent: str,
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[SpanRecord, None, None]:
        """Context manager that creates and auto-closes a trace span."""
        span_id = _new_span_id()
        record = SpanRecord(
            span_id=span_id,
            parent_id=parent_id,
            operation=operation,
            agent=agent,
            start_time=time.time(),
            attributes=attributes or {},
        )
        self.spans.append(record)

        # Also create OTEL span if available
        otel_span = None
        if self._otel_tracer:
            try:
                otel_span = self._otel_tracer.start_span(
                    name=f"{agent}/{operation}",
                    attributes={**(attributes or {}), "agent": agent},
                )
            except Exception:
                pass

        try:
            yield record
            record.status = "ok"
        except Exception as exc:
            record.status = "error"
            record.events.append({"error": str(exc), "timestamp": time.time()})
            raise
        finally:
            record.end_time = time.time()
            if otel_span:
                try:
                    otel_span.end()
                except Exception:
                    pass

    def add_event(self, span_id: str, event: dict[str, Any]) -> None:
        for s in self.spans:
            if s.span_id == span_id:
                s.events.append(event)
                return

    def to_trace_spans(self) -> list[TraceSpan]:
        """Convert internal records to API-friendly TraceSpan models."""
        result = []
        for s in self.spans:
            duration_ms = ((s.end_time or time.time()) - s.start_time) * 1000
            result.append(TraceSpan(
                span_id=s.span_id,
                parent_id=s.parent_id,
                operation=s.operation,
                agent=s.agent,
                start_time=datetime.fromtimestamp(s.start_time, tz=timezone.utc),
                end_time=datetime.fromtimestamp(s.end_time, tz=timezone.utc) if s.end_time else None,
                duration_ms=round(duration_ms, 2),
                status=s.status,
                attributes=s.attributes,
                events=s.events,
            ))
        return result


def get_tracer(trace_id: str | None = None) -> TracingManager:
    return TracingManager(trace_id)
