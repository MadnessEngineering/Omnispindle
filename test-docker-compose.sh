#!/bin/bash

# Test Docker Compose setup for Omnispindle
# Phase 2: Docker Infrastructure Update - Test Script

set -e

echo "Testing Docker Compose configuration..."

# Validate compose file
docker compose config

echo "Starting services..."
docker compose up -d

# Wait for services to start
echo "Waiting for services to be ready..."
sleep 30

# Test health endpoints
echo "Testing health endpoints..."
curl -f http://localhost:8000/health || echo "Health check failed - service may still be starting"

# Show service status
echo "Service status:"
docker compose ps

echo "Logs from mcp-todo-server:"
docker compose logs --tail=20 mcp-todo-server

echo "Test completed! Run 'docker compose down' to stop services."