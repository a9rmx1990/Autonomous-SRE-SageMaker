# AgentCore Memory Integration

## Overview

Amazon Bedrock AgentCore Memory provides persistent, semantically searchable memory for the SRE agents. The system uses it to store and retrieve incident post-mortems, failure patterns, and remediation preferences, making each subsequent incident investigation faster and more informed.

## How It Works

### Before Investigation (Context Retrieval)

When a new incident arrives, the orchestrator calls `MemoryManager.retrieve_context()` with the service name and incident description. This performs a semantic search against stored memories to find:

- **SEMANTIC**: Past incidents on the same or similar services
- **USER_PREFERENCE**: Remediation strategies that have worked before

The retrieved context is injected into the orchestrator's prompt, allowing it to reference prior experience.

### After Resolution (Context Storage)

Once an incident is resolved, the orchestrator stores:

- Incident summary (service, severity, duration)
- Root cause analysis
- Remediation action taken and outcome
- Verification results
- Lessons learned

This is stored via `MemoryManager.store_incident()` in the `incidents` namespace.

## Configuration

```bash
# Required for production memory
AGENTCORE_MEMORY_ID=your-memory-resource-id
AWS_REGION=us-east-1
```

### Creating a Memory Resource

```bash
# Via AWS CLI (when AgentCore GA APIs are available)
aws bedrock-agentcore create-memory \
  --memory-name autonomous-sre-memory \
  --description "Incident history and remediation patterns for Autonomous SRE"
```

Use the returned memory ID as `AGENTCORE_MEMORY_ID`.

## Fallback Behavior

When `AGENTCORE_MEMORY_ID` is not set or the AgentCore service is unavailable:

- The system logs a warning and continues without persistent memory
- A local in-memory dictionary stores entries for the current session
- The `retrieve_context()` call returns an empty context string
- No errors are raised; the pipeline runs normally without historical context

This ensures the application works in simulation/demo mode without any AWS services.

## Memory Namespaces

| Namespace | Content | Retrieval Type |
|-----------|---------|---------------|
| `incidents` | Post-mortems, root causes, remediations | SEMANTIC |
| `preferences` | Remediation strategies, escalation rules | USER_PREFERENCE |
| `patterns` | Recurring failure patterns | SEMANTIC |

## API

### Memory Endpoint

```
GET /api/memory
```

Returns all stored memory entries (from AgentCore or local fallback).

### Frontend

The Memory page (`/memory`) displays:
- Post-mortem viewer with expandable incident details
- Filtered entry list by type (incident/pattern/preference)
- Search across all memory content
- Explanation of the memory lifecycle
