# Omnispindle Deployment Examples

## Overview

Omnispindle v1.0.0 supports multiple deployment scenarios optimized for different use cases. This guide provides complete configuration examples for each environment.

## PyPI Installation (Recommended)

### Basic Claude Desktop Setup

```bash
# Install from PyPI
pip install omnispindle
```

**claude_desktop_config.json**:
```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "basic",
        "MCP_USER_EMAIL": "your-email@example.com"
      }
    }
  }
}
```

### Advanced Configuration

```json
{
  "mcpServers": {
    "omnispindle": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "hybrid",
        "OMNISPINDLE_TOOL_LOADOUT": "full",
        "OMNISPINDLE_FALLBACK_ENABLED": "true",
        "OMNISPINDLE_API_TIMEOUT": "15.0",
        "MCP_USER_EMAIL": "your-email@example.com",
        "MADNESS_API_URL": "https://madnessinteractive.cc/api",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "swarmonomicon"
      }
    }
  }
}
```

## Development Deployment

### Local Development

```bash
# Clone repository
git clone https://github.com/DanEdens/Omnispindle.git
cd Omnispindle

# Install dependencies
pip install -r requirements.txt

# Run stdio server
python -m src.Omnispindle.stdio_server

# Or run web server
python -m src.Omnispindle
```

**Environment Variables**:
```bash
export OMNISPINDLE_MODE=hybrid
export OMNISPINDLE_TOOL_LOADOUT=full
export MCP_USER_EMAIL=dev@example.com
export MONGODB_URI=mongodb://localhost:27017
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

### Development with Docker

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  omnispindle:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OMNISPINDLE_MODE=hybrid
      - OMNISPINDLE_TOOL_LOADOUT=basic
      - MCP_USER_EMAIL=dev@example.com
      - MADNESS_API_URL=https://madnessinteractive.cc/api
      - MONGODB_URI=mongodb://mongo:27017
      - MONGODB_DB=swarmonomicon
    depends_on:
      - mongo
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

## Production Deployment

### API-Only Production (Recommended)

**docker-compose.prod.yml**:
```yaml
version: '3.8'

services:
  omnispindle:
    image: omnispindle:v1.0.0
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - OMNISPINDLE_MODE=api
      - OMNISPINDLE_TOOL_LOADOUT=basic
      - MADNESS_API_URL=https://madnessinteractive.cc/api
      - MADNESS_AUTH_TOKEN=${MADNESS_AUTH_TOKEN}
      - MCP_USER_EMAIL=${MCP_USER_EMAIL}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 60s
      timeout: 15s
      retries: 3
      start_period: 10s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.omnispindle.rule=Host(`omnispindle.yourdomain.com`)"
      - "traefik.http.services.omnispindle.loadbalancer.server.port=8000"
```

### PM2 Production Deployment

**ecosystem.config.js**:
```javascript
module.exports = {
  apps: [
    {
      name: 'omnispindle',
      script: 'python3.13',
      args: ['-m', 'src.Omnispindle'],
      cwd: '/opt/omnispindle',
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      max_memory_restart: '500M',
      restart_delay: 1000,
      max_restarts: 5,
      env_production: {
        NODE_ENV: 'production',
        OMNISPINDLE_MODE: 'api',
        OMNISPINDLE_TOOL_LOADOUT: 'basic',
        MADNESS_API_URL: 'https://madnessinteractive.cc/api',
        MADNESS_AUTH_TOKEN: process.env.MADNESS_AUTH_TOKEN,
        MCP_USER_EMAIL: process.env.MCP_USER_EMAIL,
        PORT: 8000
      }
    }
  ]
};
```

**Deployment Script**:
```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Deploying Omnispindle v1.0.0..."

# Pull latest code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run security scan
git secrets --scan-history

# Restart PM2 process
pm2 reload ecosystem.config.js --env production

# Health check
sleep 10
curl -f http://localhost:8000/health || exit 1

echo "✅ Deployment complete!"
```

## Container Deployments

### Kubernetes Deployment

**omnispindle-deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: omnispindle
  labels:
    app: omnispindle
spec:
  replicas: 2
  selector:
    matchLabels:
      app: omnispindle
  template:
    metadata:
      labels:
        app: omnispindle
    spec:
      containers:
      - name: omnispindle
        image: omnispindle:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: OMNISPINDLE_MODE
          value: "api"
        - name: OMNISPINDLE_TOOL_LOADOUT  
          value: "basic"
        - name: MADNESS_API_URL
          value: "https://madnessinteractive.cc/api"
        - name: MADNESS_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: omnispindle-secrets
              key: auth-token
        - name: MCP_USER_EMAIL
          valueFrom:
            configMapKeyRef:
              name: omnispindle-config
              key: user-email
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 60
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: omnispindle-service
spec:
  selector:
    app: omnispindle
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

### Docker Swarm

**docker-stack.yml**:
```yaml
version: '3.8'

services:
  omnispindle:
    image: omnispindle:v1.0.0
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
    ports:
      - "8000:8000"
    environment:
      - OMNISPINDLE_MODE=api
      - OMNISPINDLE_TOOL_LOADOUT=basic
      - MADNESS_API_URL=https://madnessinteractive.cc/api
    secrets:
      - omnispindle_auth_token
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

secrets:
  omnispindle_auth_token:
    external: true
```

## Tool Loadout Examples

### Minimal Setup (Token Optimization)
```json
{
  "mcpServers": {
    "omnispindle-minimal": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "minimal",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

**Available Tools**: add_todo, query_todos, get_todo, mark_todo_complete

### Knowledge Management Focus
```json
{
  "mcpServers": {
    "omnispindle-lessons": {
      "command": "omnispindle-stdio", 
      "env": {
        "OMNISPINDLE_MODE": "api",
        "OMNISPINDLE_TOOL_LOADOUT": "lessons",
        "MCP_USER_EMAIL": "user@example.com"
      }
    }
  }
}
```

**Available Tools**: add_lesson, get_lesson, update_lesson, delete_lesson, search_lessons, grep_lessons, list_lessons

### Administrative Operations
```json
{
  "mcpServers": {
    "omnispindle-admin": {
      "command": "omnispindle-stdio",
      "env": {
        "OMNISPINDLE_MODE": "hybrid",
        "OMNISPINDLE_TOOL_LOADOUT": "admin", 
        "MCP_USER_EMAIL": "admin@example.com"
      }
    }
  }
}
```

**Available Tools**: query_todos, update_todo, delete_todo, query_todo_logs, list_projects, explain, add_explanation

## Monitoring and Maintenance

### Health Check Endpoints

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed status (if available)
curl http://localhost:8000/status

# Metrics endpoint (if enabled)
curl http://localhost:8000/metrics
```

### Log Management

```bash
# PM2 logs (remember to use timeout!)
timeout 15 pm2 logs omnispindle

# Docker logs
docker logs omnispindle-container

# Kubernetes logs
kubectl logs deployment/omnispindle
```

### Security Considerations

1. **Never commit secrets** - Git-secrets is active
2. **Use environment variables** for all sensitive configuration
3. **Enable HTTPS** in production deployments
4. **Rotate tokens regularly** - Auth0 tokens have expiration
5. **Monitor failed authentication attempts**
6. **Keep dependencies updated** - Regular security patches

## Troubleshooting

### Common Issues

**Authentication Failures**:
```bash
# Check token cache
ls -la ~/.omnispindle/

# Test API connectivity
python -c "
import os
os.environ['OMNISPINDLE_MODE'] = 'api'
from src.Omnispindle.api_client import MadnessAPIClient
client = MadnessAPIClient()
print('API connectivity test:', client.test_connection())
"
```

**Performance Issues**:
- Switch to API mode for better performance
- Use appropriate tool loadouts to reduce token usage
- Monitor memory usage with resource limits

**Connection Problems**:
- Verify network connectivity to madnessinteractive.cc
- Check firewall settings for outbound HTTPS
- Validate DNS resolution