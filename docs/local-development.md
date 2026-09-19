# Local Development

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm or yarn
- (Optional) Docker and Docker Compose
- (Optional) AWS CLI configured with credentials

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run in simulation mode (no AWS required)
SIMULATION_MODE=true uvicorn main:app --reload --port 8000
```

The API is now available at http://localhost:8000. Verify with:

```bash
curl http://localhost:8000/health
```

### Running with Real AWS

```bash
# Configure AWS credentials
aws configure

# Set environment variables
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514
export SIMULATION_MODE=false

# Optional: AgentCore Memory
export AGENTCORE_MEMORY_ID=your-memory-id

# Optional: OpenTelemetry
export OTEL_ENABLED=true
export OTEL_EXPORTER_ENDPOINT=http://localhost:4317

uvicorn main:app --reload --port 8000
```

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The dashboard is now available at http://localhost:3000.

The frontend proxies API calls to `http://localhost:8000` via Next.js rewrites configured in `next.config.js`.

## Docker Compose

```bash
# From project root
cp .env.example .env
# Edit .env as needed

docker compose up --build
```

This starts both backend (port 8000) and frontend (port 3000).

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Tests run entirely in simulation mode and require no AWS credentials.

## Development Workflow

1. Start the backend with `SIMULATION_MODE=true`
2. Start the frontend with `npm run dev`
3. Open http://localhost:3000
4. Click "Simulate Payment API Incident" on the dashboard
5. The incident detail page shows the live agent pipeline

### API Endpoints for Manual Testing

```bash
# Create a simulated incident
curl -X POST http://localhost:8000/api/simulate

# List incidents
curl http://localhost:8000/api/incidents

# Run the agent pipeline on an incident
curl -X POST http://localhost:8000/api/incidents/{id}/run

# Stream events (SSE)
curl -N http://localhost:8000/api/incidents/{id}/events

# Get trace data
curl http://localhost:8000/api/incidents/{id}/trace

# Get memory entries
curl http://localhost:8000/api/memory
```
