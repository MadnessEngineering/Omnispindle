#!/bin/bash

# Build and push Omnispindle Docker image
# Phase 2: Docker Infrastructure Update - Build Script

set -e

echo "Building Omnispindle Docker image v0.0.9..."

# Build the image with both version and latest tags
docker build \
  -t danedens31/omnispindle:0.0.9 \
  -t danedens31/omnispindle:latest \
  .

echo "Build completed successfully!"

# Test the image
echo "Testing the built image..."
docker run --rm danedens31/omnispindle:0.0.9 python --version

echo "Image test completed!"

# Push to Docker Hub (requires docker login first)
echo "Pushing to Docker Hub..."
docker push danedens31/omnispindle:0.0.9
docker push danedens31/omnispindle:latest

echo "Push completed successfully!"
echo "Images available at:"
echo "- danedens31/omnispindle:0.0.9"
echo "- danedens31/omnispindle:latest"