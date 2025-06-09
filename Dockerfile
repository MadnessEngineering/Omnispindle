# Omnispindle MCP Todo Server Dockerfile
# Multi-stage build for better efficiency

# Build stage for development dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Install dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    mosquitto-clients \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MONGODB_URI=mongodb://mongo:27017 \
    MONGODB_DB=swarmonomicon \
    MONGODB_COLLECTION=todos \
    AWSIP=mosquitto \
    AWSPORT=27017 \
    MQTT_HOST=mosquitto \
    MQTT_PORT=1883 \
    DeNa=omnispindle \
    HOST=0.0.0.0 \
    PORT=8000 \
    PYTHONPATH=/app

# Create non-root user
RUN useradd -m -s /bin/bash appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Create configuration directory if it doesn't exist
RUN mkdir -p /app/config && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; socket.socket().connect(('localhost', 8000))" || exit 1

# Expose the needed ports
EXPOSE 8080 8000 1883

# Set the entrypoint
CMD ["python", "-m", "src.Omnispindle"]

# Add metadata
LABEL maintainer="Danedens31@gmail.com"
LABEL description="Omnispindle - MCP Todo Server implementation"
LABEL version="0.1.0"
LABEL org.opencontainers.image.source="https://github.com/DanEdens/Omnispindle"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="Dan Edens"
LABEL org.opencontainers.image.title="Omnispindle MCP Todo Server"
LABEL org.opencontainers.image.description="FastMCP-based Todo Server for the Swarmonomicon project"

# MCP-specific labels
LABEL mcp.server.name="io.github.danedens31/omnispindle"
LABEL mcp.server.version="0.1.0"
LABEL mcp.protocol.version="2025-03-26"
LABEL mcp.transport.stdio="true"
LABEL mcp.transport.sse="true"
LABEL mcp.features.tools="true"
LABEL mcp.features.resources="false"
LABEL mcp.features.prompts="false"
LABEL mcp.capabilities="todo_management,project_coordination,mqtt_messaging,lesson_logging,ai_assistance,task_scheduling"
