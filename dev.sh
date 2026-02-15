#!/usr/bin/env bash
# Start both the FastAPI server and Next.js dev server.
# Usage: ./dev.sh

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo "Shutting down..."
    kill $API_PID $WEB_PID 2>/dev/null
    wait $API_PID $WEB_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Activate venv if present
if [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
fi

# Start FastAPI
echo "Starting API server on :8000..."
cd "$DIR"
uvicorn api.server:app --reload --port 8000 &
API_PID=$!

# Start Next.js
echo "Starting frontend on :3000..."
cd "$DIR/web"
npm run dev &
WEB_PID=$!

echo ""
echo "API:      http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers."

wait
