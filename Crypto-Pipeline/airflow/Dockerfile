# Custom Airflow image with Kafka 4.x CLI and providers
FROM apache/airflow:2.8.1-python3.11

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates wget bash jq openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Kafka 4.x CLI
ENV KAFKA_VERSION=4.0.0 \
    SCALA_VERSION=2.13 \
    KAFKA_HOME=/opt/kafka

RUN cd /tmp \
    && wget -q https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz \
    && tar -xzf kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz \
    && mv kafka_${SCALA_VERSION}-${KAFKA_VERSION} ${KAFKA_HOME} \
    && ln -s ${KAFKA_HOME}/bin/kafka-topics.sh /usr/local/bin/kafka-topics \
    && ln -s ${KAFKA_HOME}/bin/kafka-console-producer.sh /usr/local/bin/kafka-console-producer \
    && ln -s ${KAFKA_HOME}/bin/kafka-console-consumer.sh /usr/local/bin/kafka-console-consumer \
    && rm -f kafka_${SCALA_VERSION}-${KAFKA_VERSION}.tgz

USER airflow

# Install providers/libs in Airflow venv
# Use Airflow constraints to avoid dependency conflicts
ARG AIRFLOW_VERSION=2.8.1
ARG PYTHON_VERSION=3.11
ARG CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

RUN pip install --no-cache-dir \
    "apache-airflow-providers-docker==3.8.0" \
    "apache-airflow-providers-postgres==5.7.1" \
    --constraint "${CONSTRAINT_URL}"

# Install dbt matching project pins
RUN pip install --no-cache-dir dbt-core==1.7.4 dbt-postgres==1.7.4

ENV PATH=/home/airflow/.local/bin:${PATH}


