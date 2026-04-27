#!/bin/bash
# Privacy Nutrition Label – Start Script
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    Privacy Lens                      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Backend ────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/3]${NC} Setting up Python backend…"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
  echo "  Creating virtual environment…"
  python3 -m venv venv
fi

source venv/bin/activate
echo "  Installing dependencies…"
pip install -q -r requirements.txt

echo -e "${GREEN}  ✓ Backend dependencies ready${NC}"

# Start backend in background
echo -e "${BLUE}[2/3]${NC} Starting FastAPI backend on http://localhost:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}  ✓ Backend started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
sleep 2
echo ""

# ── Frontend ───────────────────────────────────────────────────────────────
echo -e "${BLUE}[3/3]${NC} Setting up frontend…"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "  Installing npm packages…"
  npm install
fi

echo -e "${GREEN}  ✓ Frontend dependencies ready${NC}"
echo ""
echo -e "${BOLD}Starting frontend dev server on http://localhost:5173${NC}"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Web App:  ${BOLD}http://localhost:5173${NC}"
echo -e "${GREEN}  API:      ${BOLD}http://localhost:8000${NC}"
echo -e "${GREEN}  API Docs: ${BOLD}http://localhost:8000/docs${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Extension:${NC} Load unpacked from ${SCRIPT_DIR}/extension/ in Chrome"
echo "  chrome://extensions → Developer mode → Load unpacked"
echo ""

# Handle cleanup on exit
cleanup() {
  echo ""
  echo -e "${YELLOW}Shutting down…${NC}"
  kill $BACKEND_PID 2>/dev/null || true
  echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

npm run dev
