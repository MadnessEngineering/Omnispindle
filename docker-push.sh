#!/bin/bash

# Script to build and push Omnispindle Docker images to Docker Hub
# This script assumes you've already authenticated with Docker CLI

# Set variables
DOCKER_USERNAME="danedens31"
REPO_NAME="omnispindle"
VERSION="0.1.0"
#$(grep "version=" pyproject.toml | cut -d'"' -f2 || echo "0.1.0")
LATEST_TAG="latest"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Building and pushing Omnispindle images to Docker Hub${NC}"
echo -e "Username: ${GREEN}${DOCKER_USERNAME}${NC}"
echo -e "Repository: ${GREEN}${REPO_NAME}${NC}"
echo -e "Version: ${GREEN}${VERSION}${NC}"

# Build the MCP Todo Server image
echo -e "\n${YELLOW}Building MCP Todo Server image...${NC}"
docker build -t ${DOCKER_USERNAME}/${REPO_NAME}:${VERSION} -t ${DOCKER_USERNAME}/${REPO_NAME}:${LATEST_TAG} .

# Push the images to Docker Hub
echo -e "\n${YELLOW}Pushing images to Docker Hub...${NC}"
docker push ${DOCKER_USERNAME}/${REPO_NAME}:${VERSION}
docker push ${DOCKER_USERNAME}/${REPO_NAME}:${LATEST_TAG}

echo -e "\n${GREEN}Done! Images have been pushed to Docker Hub:${NC}"
echo -e "  • ${DOCKER_USERNAME}/${REPO_NAME}:${VERSION}"
echo -e "  • ${DOCKER_USERNAME}/${REPO_NAME}:${LATEST_TAG}"
