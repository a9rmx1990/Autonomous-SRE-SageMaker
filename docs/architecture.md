# Architecture

## System Overview

The Autonomous SRE platform uses a multi-agent supervisor pattern built on the AWS Strands Agents SDK. A central orchestrator delegates investigation, remediation, and verification to specialist agents, each backed by purpose-built tools that interact with AWS services.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Dashboard                            │
│                     Next.js / React / SSE                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + SSE
┌────────────────────────────▼────────────────────────────────────┐
│                       FastAPI Backend                            │
│                      SRE Control Plane                          │
├─────────────┬──────────────┬──────────────┬─────────────────────┤
│  /api/      │  /simulate   │  /events SSE │  /trace             │
└─────────────┴──────┬───────┴──────────────┴─────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                    SREOrchestrator                               │
│                   Strands Agent (Supervisor)                     │
│                                                                 │
│  System Prompt: SRE runbook reasoning                           │
│  Tools: log_analyst_tool, remediator_tool, verifier_tool        │
└──────┬─────────────────┬─────────────────┬──────────────────────┘
       │                 │                 │
┌──────▼──────┐  ┌───────▼──────┐  ┌──────▼──────┐
│ Log Analyst │  │ Remediator   │  │  Verifier   │
│   Agent     │  │   Agent      │  │   Agent     │
└──────┬──────┘  └───────┬──────┘  └──────┬──────┘
       │                 │                 │
  CloudWatch         Boto3 APIs       Health Checks
  Logs/Alarms     (ECS, ASG, SQS)    (CW Metrics)
```

## Component Breakdown

### Frontend (Next.js 14)

Five pages: Dashboard, Incident Detail, Architecture, Observability, Memory. The Incident Detail page subscribes to Server-Sent Events for real-time agent activity updates during pipeline execution.

### Backend (FastAPI)

Stateless API layer. Manages incident lifecycle, triggers orchestrator runs as async tasks, streams events via SSE, and serves trace/memory data. In-memory incident store (production would use DynamoDB or similar).

### SREOrchestrator (Strands Agent)

The supervisor agent. Receives incidents and follows a structured reasoning flow:
1. Retrieve historical context from AgentCore Memory
2. Delegate log analysis to the Log Analyst
3. Evaluate findings and delegate remediation
4. Delegate post-remediation verification
5. Store the post-mortem in AgentCore Memory
6. Resolve the incident

### Specialist Agents

Each specialist is a Strands Agent exposed to the orchestrator as a `@tool`:

- **LogAnalyst**: Calls `fetch_cloudwatch_alarms` and `fetch_cloudwatch_logs` to gather evidence, returns structured findings with root cause, confidence, and recommendations.
- **Remediator**: Calls `execute_remediation` with safety validation. Only allowlisted actions are permitted. Supports dry-run mode.
- **Verifier**: Calls `verify_health_status` to check 7 metrics (CPU, memory, 5xx, restarts, latency, alarm state, running tasks). Returns pass/fail with details.

### Tools Layer

All tools are decorated with `@tool` from `strands-agents` and support two modes:
- **Simulation**: Returns realistic synthetic data from `PaymentIncidentSimulator`
- **Production**: Makes real boto3 calls to AWS APIs

### Memory (AgentCore)

Uses `bedrock-agentcore` MemoryClient for semantic retrieval and storage. Falls back to local in-memory dict when AgentCore is unavailable.

### Observability

Custom `TracingManager` with context-manager spans. Optionally exports to OTEL collector for X-Ray/CloudWatch integration. Traces are also served via API for the frontend trace viewer.

## Data Flow: Incident Lifecycle

```
POST /api/simulate
  → Creates Incident (status: detected)
  → Returns incident_id

POST /api/incidents/{id}/run
  → Spawns async orchestrator task
  → Orchestrator emits events to asyncio.Queue
  → SSE endpoint streams events to frontend

GET /api/incidents/{id}/events
  → SSE stream: agent_message, finding, remediation_proposed,
    remediation_executed, verification_complete, incident_resolved
```

## Deployment Topology

```
┌──────────────┐     ┌──────────────┐
│  CloudFront  │────▶│  S3 / Vercel │  (Frontend)
└──────────────┘     └──────────────┘
                            │
┌──────────────┐     ┌──────▼───────┐     ┌──────────────┐
│  CloudWatch  │◀───▶│   ECS/EC2    │────▶│   Bedrock    │
│  X-Ray       │     │  (Backend)   │     │  (Claude)    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  AgentCore   │
                     │   Memory     │
                     └──────────────┘
```
