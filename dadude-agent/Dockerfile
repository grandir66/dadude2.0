# DaDude Agent - Lightweight Docker image for network scanning
# Ottimizzato per MikroTik RouterOS 7 Container

FROM python:3.11-alpine

# Metadata
LABEL maintainer="DaDude Team"
LABEL description="Network scanning agent for DaDude inventory system"
LABEL version="1.0.0"

# Install system dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# Remove build dependencies to reduce image size
RUN apk del gcc musl-dev libffi-dev openssl-dev cargo

# Copy application code
COPY app/ ./app/
COPY config/ ./config/

# Create non-root user
RUN adduser -D -u 1000 agent
USER agent

# Expose API port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:8080/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV DADUDE_AGENT_PORT=8080

# Run the agent
CMD ["python", "-m", "app.main"]

