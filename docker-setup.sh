#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${PURPLE}=== MADNESS HIVEMIND - Omnispindle Network Configuration ===${NC}"
echo -e "${BLUE}The madness spreads: Connecting your services into a digital hivemind${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Create the external network if it doesn't exist
if ! docker network ls | grep -q madness_network; then
    echo -e "${YELLOW}Creating MADNESS HIVEMIND network...${NC}"
    docker network create madness_network
    echo -e "${GREEN}MADNESS HIVEMIND network created successfully!${NC}"
else
    echo -e "${GREEN}MADNESS HIVEMIND network already exists.${NC}"
fi

# Check for Mosquitto config
if [ ! -f "./config/mosquitto.conf" ]; then
    echo -e "${YELLOW}Creating Mosquitto configuration...${NC}"
    mkdir -p ./config
    cat > ./config/mosquitto.conf << EOL
# Mosquitto MQTT Configuration for MADNESS HIVEMIND

# Basic configuration
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout

# Default listener - binding to all interfaces
listener 1883 0.0.0.0
protocol mqtt

# WebSockets listener for web clients - binding to all interfaces
listener 9001 0.0.0.0
protocol websockets

# Allow anonymous connections with no authentication
# IMPORTANT: This is for development/testing only!
allow_anonymous true

# Set high log level for debugging
log_type all
EOL
    echo -e "${GREEN}Mosquitto configuration created.${NC}"
fi

echo ""
echo -e "${PURPLE}MADNESS HIVEMIND Setup Complete!${NC}"
echo -e "This network allows your services to communicate across projects like a collective consciousness:"
echo -e "  • ${GREEN}Omnispindle${NC} - The central neural nexus"
echo -e "  • ${GREEN}Madness Interactive${NC} - The chaotic thought processes"
echo -e "  • ${GREEN}Swarmonomicon${NC} - The codified knowledge repository"
echo ""
echo -e "To start the services run: ${YELLOW}docker compose up -d${NC}"
echo ""
echo -e "To connect other projects to this hivemind, add this to their docker-compose.yml:"
echo -e "${BLUE}networks:"
echo "  madness_network:"
echo "    external: true"
echo -e "${NC}"
echo -e "Then add ${BLUE}networks: [madness_network]${NC} to each service that needs to join the collective."
echo ""

# Ask if user wants to start the environment now
read -p "Would you like to start the Docker environment now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Docker environment..."
    docker compose up -d
fi
