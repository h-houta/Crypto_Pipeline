FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gcc build-essential netcat-openbsd iproute2 \
    librdkafka-dev libpq-dev supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "poetry==1.8.3" \
    && poetry config virtualenvs.create false

# Install project dependencies first (better layer caching)
COPY pyproject.toml poetry.lock* /app/
RUN poetry install --only main --no-interaction --no-ansi --no-root

# Copy application source
COPY producer /app/producer
COPY consumer /app/consumer
COPY alerting /app/alerting
COPY monitoring /app/monitoring

# Runtime configs
COPY docker/supervisord.conf /app/supervisord.conf
COPY docker/entrypoint.sh /app/entrypoint.sh

RUN mkdir -p /logs \
    && chmod +x /app/entrypoint.sh

ENV PYTHONPATH=/app \
    MODE=all

EXPOSE 8000 8001 9091

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["all"]


