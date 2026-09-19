# Observability

## Overview

The system provides full observability into the multi-agent pipeline through OpenTelemetry instrumentation, with native integration paths to AWS X-Ray and CloudWatch.

## Instrumentation Architecture

```
Agent Code
    │
    ▼
TracingManager (custom spans)
    │
    ▼
OpenTelemetry SDK
    │
    ▼
OTLP Exporter
    │
    ▼
OpenTelemetry Collector
    │
    ├──▶ AWS X-Ray (distributed traces)
    └──▶ CloudWatch (metrics, logs)
```

## What Is Traced

Every stage of the incident pipeline emits spans:

| Span Name | Agent/Component | Contains |
|-----------|----------------|----------|
| `orchestrator.pipeline` | SREOrchestrator | Full pipeline duration |
| `memory.retrieve` | MemoryManager | Context retrieval latency |
| `log_analyst.investigate` | LogAnalyst | Investigation duration, findings |
| `cloudwatch.fetch_alarms` | Tool | AWS API latency |
| `cloudwatch.fetch_logs` | Tool | Log volume, error count |
| `remediator.remediate` | Remediator | Action proposed, approval status |
| `remediation.execute` | Tool | Action type, resource, result |
| `verifier.verify` | Verifier | Check results, pass/fail |
| `health.check` | Tool | Individual metric values |
| `memory.store` | MemoryManager | Storage latency |

Each span includes:
- Start/end timestamps
- Duration in milliseconds
- Status (ok/error)
- Agent name
- Metadata (tool parameters, findings, metrics)

## Configuration

### Local Development (In-Memory Only)

```bash
OTEL_ENABLED=false
```

Spans are stored in memory and served via the `/api/incidents/{id}/trace` endpoint. The frontend trace viewer displays them without any external collector.

### Production (X-Ray Export)

```bash
OTEL_ENABLED=true
OTEL_EXPORTER_ENDPOINT=http://otel-collector:4317
```

### OpenTelemetry Collector Configuration

Deploy a collector with the AWS X-Ray exporter:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 256

exporters:
  awsxray:
    region: us-east-1
  awsemf:
    region: us-east-1
    namespace: AutonomousSRE
    log_group_name: /autonomous-sre/metrics

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [awsxray]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [awsemf]
```

## Trace Propagation

The `TracingManager` creates a root span for the full pipeline and child spans for each stage. In OTEL mode, trace context propagates through the standard W3C TraceContext format. When agents call tools, the active span context is inherited automatically.

### Span Hierarchy

```
orchestrator.pipeline (root)
├── memory.retrieve
├── log_analyst.investigate
│   ├── cloudwatch.fetch_alarms
│   └── cloudwatch.fetch_logs
├── remediator.remediate
│   └── remediation.execute
├── verifier.verify
│   └── health.check
└── memory.store
```

## AWS X-Ray Integration

When traces reach X-Ray, you can:

1. Open the X-Ray console in your AWS region
2. Filter by service name `autonomous-sre`
3. View the service map showing agent-to-tool-to-AWS-service relationships
4. Drill into individual traces to see span timing and metadata
5. Identify bottlenecks (model inference latency, AWS API calls)

### X-Ray Service Map

```
[SREOrchestrator] ──▶ [LogAnalyst] ──▶ [CloudWatch]
       │
       ├──▶ [Remediator] ──▶ [ECS API]
       │
       └──▶ [Verifier] ──▶ [CloudWatch]
```

## CloudWatch Integration

### Logs

All agent activity is logged with structured JSON via Python's logging module:

```json
{
  "timestamp": "2026-09-19T11:42:08Z",
  "level": "INFO",
  "agent": "SREOrchestrator",
  "incident_id": "inc-001",
  "message": "Delegating to LogAnalyst",
  "service": "payment-api"
}
```

### Metrics (via OTEL EMF Exporter)

The EMF exporter publishes custom metrics to CloudWatch:

- `agent.invocation.duration` (by agent name)
- `tool.execution.duration` (by tool name)
- `incident.resolution.duration`
- `remediation.execution.count` (by action type)

## Frontend Trace Viewer

The Observability page (`/observability`) displays:

- Incident selector
- Pipeline diagram with agent-to-tool flow
- Timeline view with color-coded spans per agent
- Expandable metadata for each span
- Duration and status indicators

This works in both simulation (in-memory spans) and production (spans also exported to X-Ray).

## What Judges Should Look At

When demonstrating observability:

1. **Trigger an incident** and wait for resolution
2. **Open the Observability page** and select the incident
3. **Walk through the trace timeline**:
   - `orchestrator.pipeline`: Full pipeline start-to-finish
   - `log_analyst.investigate`: Show investigation duration
   - `remediator.remediate`: Show action execution
   - `verifier.verify`: Show health check results
4. **If X-Ray is configured**, open the AWS X-Ray console:
   - Show the service map
   - Click into the trace
   - Show span details with AWS API calls
5. **Key point**: Every decision the agents made is visible, auditable, and traceable. Nothing is a black box.
