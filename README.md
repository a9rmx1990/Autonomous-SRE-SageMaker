# Autonomous SRE & Self-Healing Cloud Swarm

AI agents that investigate, remediate, and verify cloud incidents autonomously.

```
Incident Detected → Investigate → Root Cause → Remediate → Verify → Learn
```

## Architecture

```
                    ┌──────────────────────┐
                    │   Web Dashboard      │
                    │   Next.js / React    │
                    └──────────┬───────────┘
                               │
                    ┌──────────────────────┐
                    │      FastAPI API     │
                    │   SRE Control Plane  │
                    └──────────┬───────────┘
                               │
                  ┌─────────────────────────┐
                  │    SREOrchestrator      │
                  │     Strands Agent       │
                  └────────────┬────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        Log Analyst      Remediator        Verifier
              │                │                │
              └────────────────┼────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    AWS Services     │
                    │ CloudWatch · ECS    │
                    │ SQS · AutoScaling   │
                    └─────────────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
          AgentCore Memory            OTEL / X-Ray
```

## Features

- **Multi-Agent SRE Pipeline**: Orchestrator delegates to specialist agents (Log Analyst, Remediator, Verifier) using the Strands Agents SDK
- **Autonomous Incident Resolution**: Detect, investigate, remediate, verify, and learn from incidents without human intervention
- **Safety-First Remediation**: Allowlisted actions only, dry-run support, human approval in production mode
- **AgentCore Memory**: Stores post-mortems, failure patterns, and remediation preferences across sessions
- **Full Observability**: OpenTelemetry instrumentation with AWS X-Ray and CloudWatch integration
- **Real-Time Dashboard**: SSE-powered live event streaming, agent swarm visualization, trace viewer
- **Simulation Mode**: Complete demo without real AWS infrastructure

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agents | AWS Strands Agents SDK, Amazon Bedrock |
| Memory | Amazon Bedrock AgentCore Memory |
| Backend | Python 3.11+, FastAPI, Pydantic, Boto3 |
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, Framer Motion |
| Observability | OpenTelemetry, AWS X-Ray, CloudWatch |
| Deployment | Docker, Docker Compose |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional)
- AWS account with Bedrock access (optional for simulation mode)

### Local Development

```bash
# Clone
git clone git@github.com:a9rmx1990/Autonomous-SRE-SageMaker.git
cd Autonomous-SRE-SageMaker

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
SIMULATION_MODE=true uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### Docker

```bash
cp .env.example .env
docker compose up --build
```

## Demo

1. Open the dashboard at http://localhost:3000
2. Click **Simulate Payment API Incident**
3. Watch the agent pipeline execute in real time:
   - Orchestrator receives the incident
   - Log Analyst investigates CloudWatch logs
   - Remediator proposes and executes scaling action
   - Verifier confirms recovery
   - Post-mortem stored in AgentCore Memory
4. Visit **Observability** to inspect the trace
5. Visit **Memory** to see the stored post-mortem

See [docs/judge-demo.md](docs/judge-demo.md) for a full 3-5 minute demo script.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_REGION` | AWS region | `us-east-1` |
| `BEDROCK_MODEL_ID` | Bedrock model ID | `us.anthropic.claude-sonnet-4-20250514` |
| `AGENTCORE_MEMORY_ID` | AgentCore Memory ID | (empty) |
| `SIMULATION_MODE` | Run without real AWS | `true` |
| `OTEL_ENABLED` | Enable OpenTelemetry export | `false` |

## Project Structure

```
autonomous-sre/
├── backend/
│   ├── app/
│   │   ├── agents/        # Strands agents (orchestrator, analyst, remediator, verifier)
│   │   ├── tools/         # @tool functions (cloudwatch, infrastructure, remediation, verification)
│   │   ├── memory/        # AgentCore Memory hooks
│   │   ├── observability/ # OpenTelemetry tracing
│   │   ├── simulation/    # Payment API incident simulator
│   │   ├── api/           # FastAPI routes
│   │   ├── models/        # Pydantic models
│   │   └── config/        # Settings
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/               # Next.js pages (dashboard, incidents, architecture, observability, memory)
│   ├── hooks/             # Custom React hooks
│   ├── lib/               # API client, utilities
│   └── Dockerfile
├── docs/                  # Architecture, deployment, demo guides
├── docker-compose.yml
└── .env.example
```

## Documentation

- [Architecture](docs/architecture.md)
- [How It Works](docs/how-it-works.md)
- [Local Development](docs/local-development.md)
- [AWS Deployment](docs/aws-deployment.md)
- [AgentCore Memory](docs/agentcore.md)
- [Observability](docs/observability.md)
- [Security](docs/security.md)
- [Judge Demo Script](docs/judge-demo.md)

## Security

- No hard-coded AWS credentials; uses boto3 credential chain
- Remediation actions are allowlisted (no arbitrary LLM-generated commands)
- Human approval required in production mode
- Simulation mode clearly labeled
- Input validation on all API endpoints
- Structured logging with no secrets

## Limitations

- Simulation mode generates synthetic data; real AWS integration requires valid credentials and resources
- AgentCore Memory falls back to in-memory storage when unavailable
- Currently supports a single incident scenario (payment-api); extensible to additional services
- OpenTelemetry export requires a configured collector endpoint

## Future Improvements

- Predictive auto-scaling based on historical patterns
- Multi-service incident correlation
- Slack/PagerDuty integration for alert routing
- Custom runbook support via AgentCore Memory
- Cost-aware remediation decisions
- Canary deployment verification