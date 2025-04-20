# Docker Setup for MCP Todo Server (Omnispindle)

This document provides instructions for deploying the MCP Todo Server (Omnispindle implementation) using Docker on various platforms.

## Overview

The Docker setup for MCP Todo Server includes:

1. **MongoDB** - For storing todo items and lessons learned
2. **Mosquitto MQTT** - For event-driven communication
3. **MCP Todo Server** - The main API for todo management
4. **Todo Dashboard** - A simple web UI for managing todos

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free RAM
- 2GB of free disk space

## Quick Start

1. Run the setup script:

   ```bash
   # For macOS/Linux
   ./docker-setup.sh
   ```

2. Start the Docker environment:

   ```bash
   ./start-docker.sh
   ```

3. Access the services:
   - **Todo Dashboard**: [http://localhost:3001](http://localhost:3001)
   - **MCP Todo Server API**: [http://localhost:8080](http://localhost:8080)
   - **MQTT**: localhost:1883 (WebSockets: 9001)
   - **MongoDB**: localhost:27017

## Configuration

### Environment Variables

You can customize the deployment by modifying these environment variables in the `docker-compose.yml` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection URI | mongodb://mongodb:27017 |
| `MONGODB_DB` | MongoDB database name | swarmonomicon |
| `MONGODB_COLLECTION` | MongoDB collection for todos | todos |
| `MQTT_HOST` | MQTT broker hostname | mosquitto |
| `MQTT_PORT` | MQTT broker port | 1883 |
| `AWSIP` | Legacy MQTT host reference | mongodb |
| `AWSPORT` | Legacy MQTT port reference | 27017 |
| `DeNa` | Server hostname identifier | omnispindle |

### Volumes

The Docker setup uses these persistent volumes:

- `mongodb_data`: MongoDB data
- `mosquitto_data`: MQTT broker persistent messages
- `mosquitto_log`: MQTT broker logs

## API Endpoints

The MCP Todo Server exposes the following REST API endpoints:

- `POST /api/todos` - Add a new todo
- `GET /api/todos` - List todos (with optional filtering)
- `GET /api/todos/{id}` - Get a specific todo
- `PUT /api/todos/{id}` - Update a todo
- `POST /api/todos/{id}/complete` - Mark a todo as complete
- `DELETE /api/todos/{id}` - Delete a todo

The server also listens on the following MQTT topics:

- `mcp/+/request/#` - Receives requests
- `mcp/+/response/#` - Sends responses
- `mcp/+/error/#` - Sends error messages

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │
│  Dashboard  │────▶│  MCP Todo   │────▶│  MongoDB    │
│  (Web UI)   │     │   Server    │     │ (Database)  │
│             │     │             │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │             │
                    │  Mosquitto  │
                    │   (MQTT)    │
                    │             │
                    └─────────────┘
                           ▲
                           │
                    ┌─────────────┐
                    │             │
                    │   Clients   │
                    │             │
                    └─────────────┘
```

## Helper Scripts

The following helper scripts are included:

- `docker-setup.sh` - Prepares the Docker environment
- `start-docker.sh` - Starts the Docker containers
- `stop-docker.sh` - Stops the Docker containers
- `view-logs.sh` - Views logs from one or all containers

## Troubleshooting

### Common Issues

1. **Docker Compose Not Found**

   If you get errors about docker-compose not being found, make sure you have Docker Compose installed. You can use either the standalone `docker-compose` command or the Docker Compose plugin (`docker compose`).

2. **Port Conflicts**

   If you get port conflict errors, change the port mappings in the `docker-compose.yml` file.

3. **MongoDB Connection Issues**

   If the MCP Todo Server can't connect to MongoDB, check that the MongoDB container is running and healthy:

   ```bash
   docker compose ps mongodb
   ```

4. **MQTT Connection Issues**

   To verify MQTT connectivity:

   ```bash
   # In one terminal
   mosquitto_sub -h localhost -t test
   
   # In another terminal
   mosquitto_pub -h localhost -t test -m "hello"
   ```

## Customization

### Dashboard UI

The Todo Dashboard is a simple web UI built with HTML, CSS (Bootstrap), and JavaScript. The UI is built into the Docker image. If you want to customize it, edit the Dockerfile in the `todo-dashboard` directory.

### API Endpoints

The MCP Todo Server API endpoints are defined in the server implementation. If you need to add new endpoints, you'll need to modify the server code in the `src/fastmcp_todo_server` directory.

## Production Deployment

For production deployment, consider:

1. Enabling authentication for MongoDB and MQTT
2. Setting up TLS for secure connections
3. Implementing proper backup strategies
4. Setting up monitoring and alerting
5. Using a reverse proxy like Nginx for HTTPS support

## License

This project is licensed under the MIT License. 
