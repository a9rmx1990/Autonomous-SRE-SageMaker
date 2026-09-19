# Security

## Design Principles

1. **No arbitrary command execution**: The LLM selects from an allowlist of remediation actions. It cannot execute arbitrary shell commands, AWS CLI commands, or SDK calls.
2. **Least privilege IAM**: The deployment guide specifies minimum required permissions. No AdministratorAccess.
3. **No hard-coded credentials**: All AWS authentication uses the boto3 credential chain (environment variables, IAM roles, profiles).
4. **Simulation isolation**: Simulation mode never touches real AWS infrastructure.

## Remediation Safety

### Action Allowlist

Only these actions can be executed:

```python
ALLOWED_ACTIONS = {
    "restart_service",
    "scale_up",
    "flush_cache",
    "restart_container",
    "clear_stuck_queue",
}
```

Any action not in this set is rejected with an error, regardless of what the LLM requests.

### Validation Flow

```
LLM proposes action
    │
    ▼
Action in ALLOWED_ACTIONS? ──No──▶ Reject
    │
   Yes
    ▼
Resource ID valid? ──No──▶ Reject
    │
   Yes
    ▼
Dry-run mode? ──Yes──▶ Log only, no execution
    │
   No
    ▼
Simulation mode? ──Yes──▶ Simulate, no AWS calls
    │
   No
    ▼
Production mode ──▶ Execute via boto3
```

### Human Approval

In production mode (`SIMULATION_MODE=false`), remediation actions can require human approval before execution. The API exposes `POST /api/incidents/{id}/approve-remediation` for this purpose.

## Input Validation

- All API inputs are validated through Pydantic models
- Incident creation requires `service` and `description` fields
- Severity must be one of: `low`, `medium`, `high`, `critical`
- Resource IDs are validated before tool execution

## Credential Management

- AWS credentials are never stored in source code or configuration files
- The `.env.example` file contains no secrets
- Production deployment uses IAM task roles (ECS) or instance profiles (EC2)
- The `AGENTCORE_MEMORY_ID` is a resource identifier, not a secret

## Logging

- Structured JSON logging throughout
- No secrets, credentials, or sensitive data in log output
- Agent reasoning and tool calls are logged for auditability
- Remediation actions include before/after state

## Error Handling

- AWS API errors are caught and returned with descriptive messages
- Agent failures do not expose internal stack traces to the API consumer
- Missing configuration is detected at startup with clear error messages
- Tool timeouts are handled gracefully

## Network

- CORS is configured to allow only specified origins
- The frontend communicates with the backend via HTTP/SSE only
- No WebSocket connections that could be hijacked
- Production should use HTTPS (via ALB/CloudFront)

## Rate Limiting

- The remediation system enforces a maximum number of remediation attempts per incident (configurable, default 3)
- This prevents infinite remediation loops from runaway agent behavior
