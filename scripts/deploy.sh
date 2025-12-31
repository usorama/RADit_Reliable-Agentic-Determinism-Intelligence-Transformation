#!/bin/bash
# DAW Production Deployment Script
# Run on Hostinger VPS (72.60.204.156)

set -e

echo "=== DAW Production Deployment ==="
echo "Domain: daw.ping-gadgets.com"
echo ""

# Check for .env.prod
if [ ! -f .env.prod ]; then
    echo "ERROR: .env.prod not found!"
    echo "Copy .env.prod.example to .env.prod and fill in values"
    exit 1
fi

# Load environment
export $(grep -v '^#' .env.prod | xargs)

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Build and deploy with docker-compose
echo "Building Docker images..."
docker compose -f docker-compose.prod.yml build --no-cache

echo "Stopping existing containers..."
docker compose -f docker-compose.prod.yml down || true

echo "Starting services..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 30

# Check health
echo "Checking backend health..."
curl -f http://localhost:8000/health/live || echo "Backend health check failed"

echo "Checking frontend health..."
curl -f http://localhost:3000/ || echo "Frontend health check failed"

echo ""
echo "=== Deployment Complete ==="
echo "Access the application at: https://daw.ping-gadgets.com"
echo ""
echo "View logs with: docker compose -f docker-compose.prod.yml logs -f"
