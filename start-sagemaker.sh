#!/bin/bash
set -e

echo "=========================================================="
echo "    Autonomous SRE Swarm — Amazon SageMaker Launcher      "
echo "=========================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# 1. Ensure .env exists
if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "[Setup] Creating .env from .env.example..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

if [ ! -f "$ROOT_DIR/backend/.env" ]; then
    cp "$ROOT_DIR/.env" "$ROOT_DIR/backend/.env"
fi

# 2. Setup Backend Python Environment
echo "[1/4] Setting up Backend Python virtual environment..."
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 3. Setup Frontend Node Environment
echo "[2/4] Setting up Frontend dependencies..."
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install --quiet
fi

# 4. Launch FastAPI Backend
echo "[3/4] Starting FastAPI Backend on port 8000..."
cd "$ROOT_DIR/backend"
source .venv/bin/activate
export SIMULATION_MODE=true
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend health check
sleep 3
while ! curl -s http://127.0.0.1:8000/health > /dev/null; do
    echo "Waiting for backend server to become ready..."
    sleep 2
done
echo "Backend is healthy and listening on port 8000."

# 5. Launch Next.js Frontend
echo "[4/4] Starting Next.js Frontend on port 3000..."
cd "$ROOT_DIR/frontend"
npm run dev -- --hostname 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

sleep 5
echo ""
echo "=========================================================="
echo "   Autonomous SRE Swarm is now RUNNING on SageMaker!      "
echo "=========================================================="
echo "Backend API:      http://localhost:8000"
echo "Frontend Web UI:  http://localhost:3000"
echo ""
echo ">>> TO SHARE A LIVE PUBLIC LINK WITH ANYONE:"
echo "Open a new terminal tab in SageMaker and run:"
echo ""
echo "    npx localtunnel --port 3000"
echo ""
echo "This will output a public HTTPS URL (e.g. https://xxxx.loca.lt)"
echo "that anyone can open in their browser without AWS login."
echo "=========================================================="

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM

wait
