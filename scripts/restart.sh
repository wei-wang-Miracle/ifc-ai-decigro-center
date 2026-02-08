#!/bin/bash

# Configuration
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/bus-kernel"
AI_ENGINE_DIR="$PROJECT_ROOT/ai-engine"
FRONTEND_DIR="$PROJECT_ROOT/decigro-fe"
LOG_DIR="$PROJECT_ROOT/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[1/4] Stopping existing services...${NC}"

# Find and kill processes on ports 8080 (Backend), 8001 (AI Engine), 5173 (Frontend)
lsof -ti:8080 | xargs kill -9 2>/dev/null
lsof -ti:8001 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Java 17 Setup
echo -e "${YELLOW}[2/4] Setting up Java environment...${NC}"
if [ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]; then
    export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
    export PATH="$JAVA_HOME/bin:$PATH"
fi
echo -e "${GREEN}[INFO] Using Java: $(java -version 2>&1 | head -n 1)${NC}"

# Backend Compilation
echo -e "${YELLOW}[3/4] Cleaning and Compiling Backend (bus-kernel)...${NC}"
cd "$BACKEND_DIR" || exit
if [ -f "./mvnw" ]; then MVN_EXEC="./mvnw"; else MVN_EXEC="mvn"; fi

$MVN_EXEC install -DskipTests
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[WARN] Backend compilation had some issues, but attempting to start anyway...${NC}"
fi

# Starting Services
echo -e "${YELLOW}[4/4] Starting all services...${NC}"

# Clear old logs
rm -f "$LOG_DIR"/*.log
touch "$LOG_DIR/backend.log" "$LOG_DIR/ai-engine.log" "$LOG_DIR/frontend.log"

# Function to handle exit
cleanup() {
    echo -e "\n${RED}[INFO] Stopping all services...${NC}"
    kill $B_PID $A_PID $F_PID 2>/dev/null
    exit
}
trap cleanup INT

# 1. Start Backend
echo -e "${CYAN}[START] Backend (8080)...${NC}"
cd "$BACKEND_DIR"
$MVN_EXEC spring-boot:run > "$LOG_DIR/backend.log" 2>&1 &
B_PID=$!

# 2. Start AI Engine
echo -e "${CYAN}[START] AI Engine (8001)...${NC}"
cd "$AI_ENGINE_DIR"
export PYTHONPATH=$AI_ENGINE_DIR/src
if command -v uv &> /dev/null; then
    uv run python -m ai_engine.main > "$LOG_DIR/ai-engine.log" 2>&1 &
else
    # Fallback to python
    python3 -m ai_engine.main > "$LOG_DIR/ai-engine.log" 2>&1 &
fi
A_PID=$!

# 3. Start Frontend
echo -e "${CYAN}[START] Frontend (5173)...${NC}"
cd "$FRONTEND_DIR"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
F_PID=$!

echo -e "${GREEN}[SUCCESS] All services are starting up!${NC}"
echo -e "Backend: http://localhost:8080/api/dg/swagger-ui.html"
echo -e "AI Engine: http://localhost:8001/docs"
echo -e "Frontend: http://localhost:5173"
echo -e "${YELLOW}Aggregating logs into this console (Ctrl+C to stop everything)...${NC}"
echo "--------------------------------------------------------------------------------"

# Tail logs
tail -f "$LOG_DIR/backend.log" "$LOG_DIR/ai-engine.log" "$LOG_DIR/frontend.log"
