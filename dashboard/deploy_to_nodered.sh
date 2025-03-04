#!/bin/bash

# Deploy MQTT Status Dashboard to Node-RED
# Usage: ./deploy_to_nodered.sh [server_url] [username] [password]

# Default server URL if not provided
SERVER_URL=${1:-"http://3.134.3.199:9090"}
USERNAME=${2:-"danedens"}
PASSWORD=${3:-""}

echo "Deploying MQTT Status Dashboard to Node-RED server at $SERVER_URL"

# Set authentication if provided
AUTH_HEADER=""
if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
  # Create base64 encoded credentials
  AUTH_STRING=$(echo -n "$USERNAME:$PASSWORD" | base64)
  AUTH_HEADER="-H \"Authorization: Basic $AUTH_STRING\""
  echo "Using authentication with username: $USERNAME"
fi

# Get flows and find the next available ID
echo "Fetching current flows..."
FLOW_ID=$(curl -s "${SERVER_URL}/flows" | jq '.[] | select(.type=="tab" and .label=="Device Status Dashboard") | .id' 2>/dev/null)

if [ -n "$FLOW_ID" ]; then
  echo "Found existing Device Status Dashboard with ID: $FLOW_ID"
  echo "Will update existing flow"
  OPERATION="update"
else
  echo "No existing dashboard found, will create new one"
  OPERATION="create"
fi

# Read the flow file
FLOW_DATA=$(cat mqtt_status_lights.json)

if [ "$OPERATION" = "create" ]; then
  # Deploy the flow to Node-RED
  echo "Deploying flow to Node-RED..."
  RESULT=$(curl -s -X POST "${SERVER_URL}/flows" \
    -H "Content-Type: application/json" \
    $AUTH_HEADER \
    --data "@mqtt_status_lights.json")
else
  # Update existing flow
  echo "Updating existing flow..."
  RESULT=$(curl -s -X PUT "${SERVER_URL}/flow/${FLOW_ID}" \
    -H "Content-Type: application/json" \
    $AUTH_HEADER \
    --data "@mqtt_status_lights.json")
fi

# Check deployment result
if [[ $RESULT == *"error"* ]]; then
  echo "Error deploying flow: $RESULT"
  exit 1
else
  echo "Flow deployed successfully!"
  echo "Access the dashboard at: ${SERVER_URL}/ui"
fi
