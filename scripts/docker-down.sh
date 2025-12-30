#!/bin/bash
#
# docker-down.sh - Stop DAW Docker Infrastructure
#
# Description:
#   Stops all Docker services for the Deterministic Agentic Workbench:
#   - Neo4j (knowledge graph / memory)
#   - Redis (Celery broker + LangGraph checkpoints)
#   - MCP Servers (Git, Filesystem)
#
# Usage:
#   ./scripts/docker-down.sh [OPTIONS]
#
# Options:
#   --volumes  Remove volumes (WARNING: deletes all data)
#   --help     Show this help message
#

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
REMOVE_VOLUMES=false

print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Stop DAW Docker Infrastructure"
    echo ""
    echo "Options:"
    echo "  --volumes  Remove volumes (WARNING: deletes all data)"
    echo "  --help     Show this help message"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            print_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}DAW Docker Infrastructure Shutdown${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Docker is not running${NC}"
    echo -e "${YELLOW}Services may already be stopped${NC}"
    exit 0
fi

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}No running services found${NC}"
    echo -e "${GREEN}Infrastructure already stopped${NC}"
    exit 0
fi

# Show running containers before shutdown
echo -e "${BLUE}Currently Running Containers:${NC}"
docker-compose ps
echo ""

# Stop services
echo -e "${BLUE}Stopping Docker services...${NC}"
docker-compose down

echo ""
echo -e "${GREEN}Services stopped successfully${NC}"
echo ""

# Remove volumes if requested
if [ "$REMOVE_VOLUMES" = true ]; then
    echo -e "${RED}⚠ WARNING: Removing volumes will delete all data!${NC}"
    read -p "Are you sure? (yes/no): " -r
    echo
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${BLUE}Removing volumes...${NC}"
        docker-compose down -v
        echo ""
        echo -e "${GREEN}Volumes removed${NC}"
        echo ""
        echo -e "${YELLOW}Data has been permanently deleted from:${NC}"
        echo -e "  - Neo4j (knowledge graph data)"
        echo -e "  - Redis (LangGraph checkpoints & Celery tasks)"
        echo ""
    else
        echo -e "${GREEN}Volume removal cancelled${NC}"
        echo -e "${BLUE}Data preserved in Docker volumes${NC}"
        echo ""
    fi
else
    echo -e "${BLUE}Data preserved in Docker volumes${NC}"
    echo -e "${YELLOW}To remove data, run: $0 --volumes${NC}"
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Infrastructure stopped successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To restart: ./scripts/docker-up.sh"
echo ""
