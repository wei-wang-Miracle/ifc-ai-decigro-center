#!/bin/bash

# Configuration
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOG_DIR="$PROJECT_ROOT/logs"

# Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[INFO] Stopping existing services...${NC}"

# Find and kill processes on ports 8080 (Backend) and 5173 (Frontend)
# Using lsof to find processes listening on ports
BACKEND_PID=$(lsof -t -i:8080)
FRONTEND_PID=$(lsof -t -i:5173)

if [ -n "$BACKEND_PID" ]; then
    echo "Killing Backend (PID: $BACKEND_PID)..."
    kill -9 $BACKEND_PID
fi

if [ -n "$FRONTEND_PID" ]; then
    echo "Killing Frontend (PID: $FRONTEND_PID)..."
    kill -9 $FRONTEND_PID
fi

echo -e "${GREEN}[INFO] Cleaning logs...${NC}"
# Clean log directory, preserving the directory itself
rm -rf "$LOG_DIR"/*

echo -e "${GREEN}[INFO] Restarting services...${NC}"
# Execute start.sh
exec "$PROJECT_ROOT/scripts/start.sh"
