FROM python:3.11-slim

WORKDIR /app/monitoring

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential librdkafka-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    confluent-kafka==2.3.0 \
    psycopg2-binary==2.9.9 \
    prometheus-client==0.19.0 \
    requests==2.31.0

COPY monitoring/throughput_monitor.py .

CMD ["python", "throughput_monitor.py"]


