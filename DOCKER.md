# Docker Setup for MCP Todo Server (Omnispindle)

This document provides instructions for deploying the MCP Todo Server (Omnispindle implementation) using Docker on various platforms.

## Overview

The Docker setup for MCP Todo Server includes:

1. **MongoDB** - For storing todo items and lessons learned
2. **Mosquitto MQTT** - For event-driven communication
3. **MCP Todo Server** - The main API for todo management
4. **Todo Dashboard** - Node-red web UI for managing todos (Coming Soon)

## Prerequisites

- Docker and Docker Compose installed
- At least 4GB of free RAM
- 2GB of free disk space

## Quick Start

1. Run the setup script to create your Mad network:

   ```bash
   # For macOS/Linux
   ./docker-setup.sh
   ```

2. Start the Docker environment:

   ```bash
   docker compose up -d
   ```

3. Access the services:
   - **MCP Todo Server API**: [http://localhost:8000/sse](http://localhost:8000/sse)
   - **MQTT**: localhost:1883 (WebSockets: 9001)
   - **MongoDB**: localhost:27017

## The MADNESS HIVEMIND Network

The MADNESS HIVEMIND is a shared Docker network that allows multiple projects to communicate with each other as part of a digital collective consciousness. It connects the Omnispindle, Madness Interactive, and Swarmonomicon projects into a single, unified ecosystem of chaotic intelligence.

### Connecting Other Projects

To connect other projects to the MADNESS HIVEMIND network, add the following to their `docker-compose.yml` files:

```yaml
networks:
  madness_network:
    external: true
```

Then, add the network to each service that needs to join the collective:

```yaml
services:
  your_service:
    # ... other configuration ...
    networks:
      - madness_network
```

### Inter-Project Communication

Services on the MADNESS HIVEMIND network can communicate with each other using their service names as neural pathways:

- MongoDB: `mongo:27017`
- MQTT: `mosquitto:1883`
- MCP Todo Server: `mcp-todo-server:8000`

## Configuration

### Environment Variables

You can customize the deployment by modifying these environment variables in the `docker-compose.yml` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection URI | mongodb://mongo:27017 |
| `MONGODB_DB` | MongoDB database name | swarmonomicon |
| `MONGODB_COLLECTION` | MongoDB collection for todos | todos |
| `MQTT_HOST` | MQTT broker hostname | mosquitto |
| `MQTT_PORT` | MQTT broker port | 1883 |
| `AWSIP` | Legacy MQTT host reference | AWS_IP_ADDRESS |
| `AWSPORT` | Legacy MQTT port reference | 1883 |
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
              ┌────────────┴────────────┐
              │                         │
      ┌───────┴──────┐         ┌───────┴──────┐
      │              │         │              │
      │ Madness      │         │ Swarmonomicon│
      │ Interactive  │         │              │
      │              │         │              │
      └──────────────┘         └──────────────┘
```

## Helper Scripts

The following helper scripts are included:

- `docker-setup.sh` - Prepares the Docker environment and creates the MADNESS HIVEMIND network

## Troubleshooting

### Common Issues

1. **Docker Compose Not Found**

   If you get errors about docker compose not being found, make sure you have Docker Compose installed. Modern Docker includes the `docker compose` plugin by default. If using an older version, you can install the standalone `docker-compose` command, but the plugin syntax is recommended.

2. **Port Conflicts**

   If you get port conflict errors, change the port mappings in the `docker-compose.yml` file.

3. **MongoDB Connection Issues**

   If the MCP Todo Server can't connect to MongoDB, check that the MongoDB container is running and healthy:

   ```bash
   docker compose ps mongo
   ```

4. **MQTT Connection Issues**

   To verify MQTT connectivity:

   ```bash
   # In one terminal
   mosquitto_sub -h localhost -t test
   
   # In another terminal
   mosquitto_pub -h localhost -t test -m "hello"
   ```

5. **Network Issues**

   If services can't connect to each other, verify the MADNESS HIVEMIND network is set up correctly:

   ```bash
   docker network inspect madness_network
   ```

## Production Deployment

For production deployment, consider:

1. Enabling authentication for MongoDB and MQTT
2. Setting up TLS for secure connections
3. Implementing proper backup strategies
4. Setting up monitoring and alerting
5. Using a reverse proxy like Nginx for HTTPS support

## License

This project is licensed under the MIT License. 
