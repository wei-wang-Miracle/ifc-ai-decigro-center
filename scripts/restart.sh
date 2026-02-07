#!/bin/bash

# Configuration
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/bus-kernel"
LOG_DIR="$PROJECT_ROOT/logs"

# Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[INFO] Stopping existing services...${NC}"

# Find and kill processes on ports 8080 (Backend) and 5173 (Frontend)
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

# Java Setup (Copied from start.sh to ensure Maven uses the correct Java version)
JAVA_HOME_CANDIDATE=""

if [ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]; then
    JAVA_HOME_CANDIDATE="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
elif [ -n "$JAVA_HOME" ] && "$JAVA_HOME/bin/java" -version 2>&1 | grep -q "version \"17"; then
    JAVA_HOME_CANDIDATE="$JAVA_HOME"
fi

if [ -n "$JAVA_HOME_CANDIDATE" ]; then
    export JAVA_HOME="$JAVA_HOME_CANDIDATE"
    export PATH="$JAVA_HOME/bin:$PATH"
    echo -e "${GREEN}[INFO] Using Java 17 at: $JAVA_HOME${NC}"
else
    echo -e "${YELLOW}[WARN] Java 17 not specifically found. Using system Java. Maven might fail if version < 17.${NC}"
fi

echo -e "${GREEN}[INFO] Cleaning and Compiling Backend...${NC}"
cd "$BACKEND_DIR" || exit

# Check if Maven wrapper exists, else use mvn
if [ -f "./mvnw" ]; then
    MVN_EXEC="./mvnw"
else
    MVN_EXEC="mvn"
fi

$MVN_EXEC clean package -DskipTests
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Compilation failed! Aborting restart.${NC}"
    exit 1
fi

echo -e "${GREEN}[INFO] Restarting services...${NC}"
# Execute start.sh
exec "$PROJECT_ROOT/scripts/start.sh"
