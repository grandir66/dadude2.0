# DaDude - The Dude MikroTik Connector
# Dockerfile

FROM python:3.11-slim

# Metadata
LABEL maintainer="Domarc Srl"
LABEL description="The Dude MikroTik Connector API"
LABEL version="1.0.0"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Rome

# Install git (required for auto-update functionality)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Create directories
RUN mkdir -p /app/data /app/logs

# Non-root user
RUN useradd -m -u 1000 dadude && \
    chown -R dadude:dadude /app
USER dadude

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
