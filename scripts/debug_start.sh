#!/bin/bash
set -x
# Configuration
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_DIR="$PROJECT_ROOT/bus-kernel"
FRONTEND_DIR="$PROJECT_ROOT/decigro-fe"
LOG_DIR="$PROJECT_ROOT/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Color Codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}[INFO] Starting DeciGro Center Local Environment...${NC}"

# 1. Java Setup
# Try to find Java 17 specifically
JAVA_HOME_CANDIDATE=""

if [ -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]; then
    JAVA_HOME_CANDIDATE="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
elif [ -n "$JAVA_HOME" ] && "$JAVA_HOME/bin/java" -version 2>&1 | grep -q "version \"17"; then
    JAVA_HOME_CANDIDATE="$JAVA_HOME"
fi

if [ -n "$JAVA_HOME_CANDIDATE" ]; then
    export JAVA_HOME="$JAVA_HOME_CANDIDATE"
    export PATH="$JAVA_HOME/bin:$PATH"
    JAVA_EXEC="$JAVA_HOME/bin/java"
    echo -e "${GREEN}[INFO] Using Java 17 at: $JAVA_HOME${NC}"
else
    # Fallback to system java
    JAVA_EXEC="java"
    echo -e "${YELLOW}[WARN] Java 17 not specifically found. Using system Java. Maven might fail if version < 17.${NC}"
fi

$JAVA_EXEC -version
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Java not found or invalid.${NC}"
    exit 1
fi

# 2. Start Backend
echo -e "${GREEN}[INFO] Starting Backend (bus-kernel)...${NC}"
cd "$BACKEND_DIR"

# Check if Maven wrapper exists, else use mvn
if [ -f "./mvnw" ]; then
    MVN_EXEC="./mvnw"
else
    MVN_EXEC="mvn"
fi

# Run in background
mkdir -p "$PROJECT_ROOT/target/tmp"
$MVN_EXEC spring-boot:run -Dspring-boot.run.jvmArguments="-Djava.io.tmpdir=$PROJECT_ROOT/target/tmp" &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# 3. Start Frontend
echo -e "${GREEN}[INFO] Starting Frontend (decigro-fe)...${NC}"
cd "$FRONTEND_DIR"

if ! command -v npm &> /dev/null; then
    echo -e "${RED}[ERROR] npm not found.${NC}"
    kill $BACKEND_PID
    exit 1
fi

# Run in background
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo -e "${GREEN}[SUCCESS] Services started!${NC}"
echo -e "Logs streaming to console..."
echo -e "Access Frontend at: http://localhost:5173"
echo -e "Press Ctrl+C to stop services..."

# Wait for user to stop
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
