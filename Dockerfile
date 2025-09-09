# Omnispindle MCP Todo Server Dockerfile
# Multi-stage build for better efficiency

# Build stage for development dependencies
FROM python:3.13-slim as builder

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
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    mosquitto-clients \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMNISPINDLE_MODE=api \
    OMNISPINDLE_TOOL_LOADOUT=basic \
    MADNESS_API_URL=https://madnessinteractive.cc/api \
    MQTT_HOST=mosquitto \
    MQTT_PORT=1883 \
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

# Health check for API endpoints
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || python -c "import requests; requests.get('http://localhost:8000/health', timeout=5).raise_for_status()" || exit 1

# Expose the needed ports
EXPOSE 8080 8000 1883

# Set the entrypoint
CMD ["python", "-m", "src.Omnispindle"]

# Add metadata
LABEL maintainer="Danedens31@gmail.com"
LABEL description="Omnispindle - MCP Todo Server implementation"
LABEL version="0.0.9"
LABEL org.opencontainers.image.source="https://github.com/DanEdens/Omnispindle"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="Dan Edens"
LABEL org.opencontainers.image.title="Omnispindle MCP Todo Server"
LABEL org.opencontainers.image.description="API-first MCP Todo Server for Madness Interactive ecosystem"
LABEL org.opencontainers.image.version="0.0.9"
LABEL org.opencontainers.image.created="2025-09-09"

# MCP-specific labels
LABEL mcp.server.name="io.github.danedens31/omnispindle"
LABEL mcp.server.version="1.0.9"
LABEL mcp.protocol.version="2025-03-26"
LABEL mcp.transport.stdio="true"
LABEL mcp.transport.sse="true"
LABEL mcp.features.tools="true"
LABEL mcp.features.resources="false"
LABEL mcp.features.prompts="false"
LABEL mcp.capabilities="todo_management,api_client,auth0_integration,hybrid_mode,mqtt_messaging"
