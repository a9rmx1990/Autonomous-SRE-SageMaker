# How It Works

## The Problem

Traditional monitoring tells you **something is broken**. Engineers must then manually investigate logs, form hypotheses, apply fixes, verify recovery, and document what happened. This takes time, context switching, and tribal knowledge.

## The Solution

This system automates the full SRE incident lifecycle through a multi-agent AI pipeline:

```
What broke? → Why? → What should we do? → Is it safe? → Did it work? → What did we learn?
```

## Pipeline Stages

### 1. Incident Detection

A CloudWatch alarm fires or an incident is manually triggered. The system creates an incident record with service, severity, and initial context.

In simulation mode, the `PaymentIncidentSimulator` generates realistic CloudWatch alarm data, log entries with stack traces, and degraded metrics that mirror a real ECS container crash scenario.

### 2. Orchestration

The `SREOrchestrator` (a Strands Agent with supervisor capabilities) receives the incident. Before starting investigation, it queries AgentCore Memory for any previous incidents on the same service to inform its approach.

The orchestrator does not perform investigation directly. It delegates to specialist agents and synthesizes their findings.

### 3. Investigation

The `LogAnalyst` agent is invoked with the service name and incident context. It:
- Fetches active CloudWatch alarms for the service
- Pulls recent log entries looking for errors, stack traces, and anomalies
- Analyzes patterns (CPU spikes, memory pressure, container restarts, 5xx rates)
- Returns structured findings with: root cause, confidence level, severity, affected resources, and recommended next action

### 4. Decision

Based on the Log Analyst findings, the `Remediator` agent determines a safe remediation action. It:
- Evaluates the root cause against available actions
- Selects from the allowlist: `restart_service`, `scale_up`, `flush_cache`, `restart_container`, `clear_stuck_queue`
- Validates the action is appropriate for the resource type
- Proposes the action with justification and risk assessment

The application never executes arbitrary LLM-generated AWS commands. Every action must match an entry in `ALLOWED_ACTIONS`.

### 5. Execution

In simulation mode, actions auto-approve. In production mode, the system pauses for human approval via the API (`POST /approve-remediation`).

Once approved, the remediation executes through explicit boto3 functions mapped to each allowed action. The simulator advances to the "recovered" stage to reflect the fix.

### 6. Verification

The `Verifier` agent checks 7 health indicators:
- CPU utilization (must be < 80%)
- Memory utilization (must be < 85%)
- HTTP 5xx error rate (must be < 5%)
- Container restart count (must be 0)
- P99 latency (must be < 500ms)
- CloudWatch alarm state (must not be ALARM)
- Running task count (must meet desired count)

If checks fail, the orchestrator can decide whether to attempt additional remediation (with a loop limit to prevent infinite retries).

### 7. Memory

After resolution, the orchestrator stores the full incident context in AgentCore Memory:
- Incident summary and root cause
- Remediation that was applied
- Verification results
- Lessons learned and recommendations

This context is retrieved on future incidents to improve investigation speed and remediation accuracy.

### 8. Observability

Every stage is instrumented with spans via the `TracingManager`. When OTEL is enabled, these export to AWS X-Ray via the OpenTelemetry collector. The frontend trace viewer displays the full pipeline execution with timing, status, and metadata for each step.
