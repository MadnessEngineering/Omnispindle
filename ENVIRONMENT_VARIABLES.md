# Omnispindle Environment Variables Reference

## Overview

Omnispindle v1.0.0 uses environment variables for all configuration, ensuring security and deployment flexibility. This document provides a comprehensive reference for all supported variables.

## Core Operation Settings

### OMNISPINDLE_MODE
**Purpose**: Controls the operation mode of the MCP server  
**Values**: `api`, `hybrid`, `local`, `auto`  
**Default**: `hybrid`  
**Description**: 
- `api` - Pure API mode, all calls to madnessinteractive.cc/api (recommended for production)
- `hybrid` - API-first with MongoDB fallback (default, most reliable)
- `local` - Direct MongoDB connections only (legacy, local development)
- `auto` - Automatically choose best performing mode

**Example**:
```bash
export OMNISPINDLE_MODE=api
```

### OMNISPINDLE_TOOL_LOADOUT
**Purpose**: Configures which MCP tools are available to reduce token usage  
**Values**: `full`, `basic`, `minimal`, `lessons`, `admin`, `hybrid_test`  
**Default**: `full`  
**Description**:
- `full` - All 22 tools available
- `basic` - Essential todo management (7 tools)
- `minimal` - Core functionality only (4 tools)
- `lessons` - Knowledge management focus (7 tools)
- `admin` - Administrative tools (6 tools)
- `hybrid_test` - Testing hybrid functionality (6 tools)

**Example**:
```bash
export OMNISPINDLE_TOOL_LOADOUT=basic
```

### OMNISPINDLE_FALLBACK_ENABLED
**Purpose**: Enable/disable fallback to local database in hybrid mode  
**Values**: `true`, `false`  
**Default**: `true`  
**Description**: When enabled, hybrid mode will fall back to local MongoDB if API calls fail

**Example**:
```bash
export OMNISPINDLE_FALLBACK_ENABLED=true
```

### OMNISPINDLE_API_TIMEOUT
**Purpose**: API request timeout in seconds  
**Values**: Numeric (seconds)  
**Default**: `10.0`  
**Description**: Timeout for HTTP requests to the API server

**Example**:
```bash
export OMNISPINDLE_API_TIMEOUT=15.0
```

## Authentication Configuration

### MADNESS_AUTH_TOKEN
**Purpose**: JWT token for API authentication  
**Values**: JWT token string  
**Default**: None (triggers device flow authentication)  
**Description**: Primary authentication method via Auth0. If not provided, automatic device flow authentication will be initiated.

**Example**:
```bash
export MADNESS_AUTH_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### MADNESS_API_KEY
**Purpose**: API key for alternative authentication  
**Values**: API key string  
**Default**: None  
**Description**: Alternative authentication method. JWT tokens take precedence over API keys.

**Example**:
```bash
export MADNESS_API_KEY=your_api_key_here
```

### MCP_USER_EMAIL
**Purpose**: User email for context isolation and identification  
**Values**: Valid email address  
**Default**: None  
**Description**: Required for user context isolation. All operations are scoped to this user.

**Example**:
```bash
export MCP_USER_EMAIL=user@example.com
```

### MADNESS_API_URL
**Purpose**: Base URL for API server  
**Values**: Valid URL  
**Default**: `https://madnessinteractive.cc/api`  
**Description**: API endpoint for all HTTP requests in api/hybrid modes

**Example**:
```bash
export MADNESS_API_URL=https://madnessinteractive.cc/api
```

## Database Configuration (Local/Hybrid Modes)

### MONGODB_URI
**Purpose**: MongoDB connection string  
**Values**: MongoDB URI  
**Default**: `mongodb://localhost:27017`  
**Description**: Connection string for local MongoDB instance. Used in local and hybrid modes.

**Example**:
```bash
export MONGODB_URI=mongodb://localhost:27017
export MONGODB_URI=mongodb://user:pass@mongo-server:27017/dbname
export MONGODB_URI=mongodb+srv://cluster.mongodb.net/dbname
```

### MONGODB_DB
**Purpose**: MongoDB database name  
**Values**: Database name string  
**Default**: `swarmonomicon`  
**Description**: Name of the MongoDB database to use for storage

**Example**:
```bash
export MONGODB_DB=swarmonomicon
```

## MQTT Configuration

### MQTT_HOST / AWSIP
**Purpose**: MQTT broker hostname  
**Values**: Hostname or IP address  
**Default**: `localhost`  
**Description**: MQTT broker for real-time messaging. Both variable names are supported for backward compatibility.

**Example**:
```bash
export MQTT_HOST=mqtt.example.com
# or
export AWSIP=52.44.236.251
```

### MQTT_PORT / AWSPORT
**Purpose**: MQTT broker port  
**Values**: Port number  
**Default**: `3003`  
**Description**: Port for MQTT broker connection

**Example**:
```bash
export MQTT_PORT=1883
# or  
export AWSPORT=3003
```

## Web Server Configuration

### PORT
**Purpose**: HTTP server port  
**Values**: Port number  
**Default**: `8000`  
**Description**: Port for the web server to bind to

**Example**:
```bash
export PORT=8080
```

### HOST
**Purpose**: HTTP server bind address  
**Values**: IP address or hostname  
**Default**: `0.0.0.0` (all interfaces)  
**Description**: Address for the web server to bind to. Fixed to 0.0.0.0 for Docker compatibility.

## Development and Testing

### NODE_ENV
**Purpose**: Environment indicator  
**Values**: `development`, `production`, `test`  
**Default**: None  
**Description**: Standard environment indicator for different deployment contexts

**Example**:
```bash
export NODE_ENV=production
```

### NR_PASS
**Purpose**: Node-RED password for dashboard integration  
**Values**: Password string  
**Default**: None  
**Description**: Password for Node-RED dashboard authentication

**Example**:
```bash
export NR_PASS=your_node_red_password
```

## Configuration Examples

### Development Setup
```bash
# Core settings
export OMNISPINDLE_MODE=hybrid
export OMNISPINDLE_TOOL_LOADOUT=full
export OMNISPINDLE_FALLBACK_ENABLED=true

# Authentication
export MCP_USER_EMAIL=dev@example.com
export MADNESS_API_URL=https://madnessinteractive.cc/api

# Local database
export MONGODB_URI=mongodb://localhost:27017
export MONGODB_DB=swarmonomicon

# MQTT
export MQTT_HOST=localhost
export MQTT_PORT=1883

# Server
export PORT=8000
```

### Production API-Only Setup
```bash
# Core settings - API only for production
export OMNISPINDLE_MODE=api
export OMNISPINDLE_TOOL_LOADOUT=basic
export OMNISPINDLE_API_TIMEOUT=15.0

# Authentication - from secure secrets
export MADNESS_AUTH_TOKEN=${AUTH_TOKEN_SECRET}
export MCP_USER_EMAIL=${USER_EMAIL_SECRET}
export MADNESS_API_URL=https://madnessinteractive.cc/api

# Server
export PORT=8000
export NODE_ENV=production
```

### Testing Setup
```bash
# Core settings - hybrid test tools
export OMNISPINDLE_MODE=hybrid
export OMNISPINDLE_TOOL_LOADOUT=hybrid_test
export OMNISPINDLE_FALLBACK_ENABLED=true

# Authentication
export MCP_USER_EMAIL=test@example.com

# Local database for testing
export MONGODB_URI=mongodb://localhost:27017
export MONGODB_DB=omnispindle_test

# MQTT
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

### Minimal Token Usage Setup
```bash
# Minimal tools to reduce AI token consumption
export OMNISPINDLE_MODE=api
export OMNISPINDLE_TOOL_LOADOUT=minimal
export MCP_USER_EMAIL=user@example.com
export MADNESS_AUTH_TOKEN=${AUTH_TOKEN}
```

## Security Considerations

### Sensitive Variables
The following variables contain sensitive information and should be handled securely:

- `MADNESS_AUTH_TOKEN` - JWT authentication token
- `MADNESS_API_KEY` - API authentication key
- `MONGODB_URI` - May contain database credentials
- `NR_PASS` - Node-RED dashboard password

### Best Practices

1. **Never commit secrets to version control** - Git-secrets is active to prevent this
2. **Use secure secret management** in production (Kubernetes secrets, Docker secrets, etc.)
3. **Rotate tokens regularly** - Auth0 tokens have expiration dates
4. **Use environment-specific configurations** - Different settings for dev/staging/prod
5. **Validate URLs and endpoints** - Ensure API URLs are legitimate
6. **Monitor for credential exposure** - Regular security audits

### Example Secure Deployment

**Docker Compose with Secrets**:
```yaml
version: '3.8'

services:
  omnispindle:
    image: omnispindle:v1.0.0
    environment:
      - OMNISPINDLE_MODE=api
      - OMNISPINDLE_TOOL_LOADOUT=basic
      - MADNESS_API_URL=https://madnessinteractive.cc/api
      - MCP_USER_EMAIL=${MCP_USER_EMAIL}
    secrets:
      - source: auth_token
        target: /run/secrets/MADNESS_AUTH_TOKEN
      - source: api_key
        target: /run/secrets/MADNESS_API_KEY

secrets:
  auth_token:
    external: true
  api_key:
    external: true
```

**Kubernetes ConfigMap and Secret**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: omnispindle-config
data:
  OMNISPINDLE_MODE: "api"
  OMNISPINDLE_TOOL_LOADOUT: "basic"
  MADNESS_API_URL: "https://madnessinteractive.cc/api"
  MCP_USER_EMAIL: "user@example.com"
---
apiVersion: v1
kind: Secret
metadata:
  name: omnispindle-secrets
type: Opaque
data:
  MADNESS_AUTH_TOKEN: <base64-encoded-token>
  MADNESS_API_KEY: <base64-encoded-key>
```

## Variable Precedence

Variables are resolved in the following order:

1. **Command line environment variables** (highest precedence)
2. **Docker/container environment variables**
3. **System environment variables**
4. **Default values** (lowest precedence)

## Validation and Troubleshooting

### Variable Validation
```bash
# Check current configuration
python -c "
import os
print('Mode:', os.getenv('OMNISPINDLE_MODE', 'hybrid'))
print('Loadout:', os.getenv('OMNISPINDLE_TOOL_LOADOUT', 'full'))
print('API URL:', os.getenv('MADNESS_API_URL', 'https://madnessinteractive.cc/api'))
print('User Email:', os.getenv('MCP_USER_EMAIL', 'Not set'))
print('Auth Token:', 'Set' if os.getenv('MADNESS_AUTH_TOKEN') else 'Not set')
"
```

### Common Issues

**Missing MCP_USER_EMAIL**:
```
Error: MCP_USER_EMAIL environment variable is required
```
Solution: Set the user email variable

**Invalid Mode**:
```
Error: Invalid OMNISPINDLE_MODE value: 'invalid'
```
Solution: Use one of: api, hybrid, local, auto

**API Authentication Failure**:
```
Error: API authentication failed
```
Solution: Check MADNESS_AUTH_TOKEN or run device flow authentication

**Database Connection Issues**:
```
Error: Could not connect to MongoDB
```
Solution: Verify MONGODB_URI and ensure MongoDB is running