#!/bin/bash
#
# docker-up.sh - Start DAW Docker Infrastructure
#
# Description:
#   Starts all required Docker services for the Deterministic Agentic Workbench:
#   - Neo4j (knowledge graph / memory)
#   - Redis (Celery broker + LangGraph checkpoints)
#   - MCP Servers (Git, Filesystem)
#
# Usage:
#   ./scripts/docker-up.sh [OPTIONS]
#
# Options:
#   --build    Force rebuild of images
#   --detach   Run in detached mode (default)
#   --logs     Follow logs after startup
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
BUILD_FLAG=""
DETACH_FLAG="-d"
FOLLOW_LOGS=false

print_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Start DAW Docker Infrastructure"
    echo ""
    echo "Options:"
    echo "  --build    Force rebuild of images"
    echo "  --detach   Run in detached mode (default)"
    echo "  --logs     Follow logs after startup"
    echo "  --help     Show this help message"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG="--build"
            shift
            ;;
        --detach)
            DETACH_FLAG="-d"
            shift
            ;;
        --logs)
            FOLLOW_LOGS=true
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
echo -e "${BLUE}DAW Docker Infrastructure Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo -e "${GREEN}.env file created. Please update with your actual credentials.${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
    echo ""
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    echo -e "${YELLOW}Please start Docker Desktop and try again${NC}"
    exit 1
fi

echo -e "${GREEN}Docker is running${NC}"
echo ""

# Start services
echo -e "${BLUE}Starting Docker services...${NC}"
docker-compose up $DETACH_FLAG $BUILD_FLAG

echo ""
echo -e "${GREEN}Services starting...${NC}"
echo ""

# Wait for health checks
if [ "$DETACH_FLAG" = "-d" ]; then
    echo -e "${BLUE}Waiting for services to be healthy...${NC}"
    echo ""

    # Wait for Neo4j
    echo -n "Neo4j: "
    until docker-compose exec -T neo4j curl -f http://localhost:7474 > /dev/null 2>&1; do
        echo -n "."
        sleep 2
    done
    echo -e " ${GREEN}✓ Ready${NC}"

    # Wait for Redis
    echo -n "Redis: "
    until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}✓ Ready${NC}"

    echo ""
    echo -e "${GREEN}All services are ready!${NC}"
    echo ""

    # Display service URLs
    echo -e "${BLUE}Service URLs:${NC}"
    echo -e "  Neo4j Browser:  ${GREEN}http://localhost:7474${NC}"
    echo -e "  Neo4j Bolt:     ${GREEN}bolt://localhost:7687${NC}"
    echo -e "  Redis:          ${GREEN}localhost:6379${NC}"
    echo ""

    # Display credentials
    echo -e "${YELLOW}Default Credentials (from docker-compose.yml):${NC}"
    echo -e "  Neo4j: ${YELLOW}neo4j / daw_password_change_me${NC}"
    echo -e "  ${RED}⚠ Change these credentials in production!${NC}"
    echo ""

    # Show running containers
    echo -e "${BLUE}Running Containers:${NC}"
    docker-compose ps
    echo ""
fi

# Follow logs if requested
if [ "$FOLLOW_LOGS" = true ]; then
    echo -e "${BLUE}Following logs (Ctrl+C to exit)...${NC}"
    echo ""
    docker-compose logs -f
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Infrastructure started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: ./scripts/docker-down.sh"
echo ""
