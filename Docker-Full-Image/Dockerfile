FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH=/app \
    MODE=all

# Build arguments
ARG APP_SRC=crypto-pipeline
ARG GIT_REPO_URL
ARG GIT_REF=main

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gcc \
    build-essential \
    netcat-openbsd \
    iproute2 \
    git \
    librdkafka-dev \
    libpq-dev \
    supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir "poetry==1.8.3" \
    && poetry config virtualenvs.create false \
    && poetry config installer.max-workers 10

# Clone application source from Git and install dependencies
# Provide GIT_REPO_URL (required), GIT_REF (branch/tag, default: main), and APP_SRC (subdir inside repo)
RUN git clone --depth 1 --branch "${GIT_REF}" "${GIT_REPO_URL}" /tmp/src \
    && mkdir -p /app \
    && cp -r "/tmp/src/${APP_SRC}/." /app \
    && rm -rf /tmp/src \
    && poetry install --only main --no-interaction --no-ansi --no-root \
    && poetry cache clear --all pypi

# Copy runtime configuration files
COPY supervisord.conf /app/supervisord.conf
COPY entrypoint.sh /app/entrypoint.sh

# Create necessary directories and set permissions
RUN mkdir -p /logs /tmp/supervisor \
    && chmod +x /app/entrypoint.sh \
    && chmod 755 /app/supervisord.conf \
    && chown -R root:root /app

# Expose ports for services
EXPOSE 8000 8001 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9091/metrics', timeout=5)" || exit 1

# Set entrypoint and default command
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["all"]


