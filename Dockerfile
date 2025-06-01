# Omnispindle MCP Todo Server Dockerfile
# Multi-stage build with UV package manager

# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy project configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    mosquitto-clients \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv in runtime stage
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY Omnispindle/ ./Omnispindle/

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
    PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN useradd -m -s /bin/bash appuser

# Create configuration directory if it doesn't exist
RUN mkdir -p /app/config && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import socket; socket.socket().connect(('localhost', 8000))" || exit 1

# Expose the needed ports
EXPOSE 8080 8000 1883

# Set the entrypoint using uv and new package structure
CMD ["uv", "run", "-m", "Omnispindle"]

# Add metadata
LABEL maintainer="Danedens31@gmail.com"
LABEL description="Omnispindle - MCP Todo Server implementation"
LABEL version="0.1.0"
LABEL org.opencontainers.image.source="https://github.com/DanEdens/Omnispindle"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="Dan Edens"
LABEL org.opencontainers.image.title="Omnispindle MCP Todo Server"
LABEL org.opencontainers.image.description="FastMCP-based Todo Server for the Swarmonomicon project"
