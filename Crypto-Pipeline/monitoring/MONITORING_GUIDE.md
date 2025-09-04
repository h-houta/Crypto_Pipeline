# 📊 Crypto Pipeline Monitoring Guide

## Overview

This guide covers the comprehensive monitoring stack for your crypto pipeline, including Prometheus metrics collection, Grafana dashboards, and Airflow-specific monitoring.

## 🏗️ Monitoring Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Airflow       │    │   Producer      │    │   Consumer      │
│   Webserver     │    │   (Coinbase)    │    │   (PostgreSQL)  │
│   Port: 8080    │    │   Port: 8000    │    │   Port: 8001    │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Airflow       │    │   Producer      │    │   Consumer      │
│   Exporter      │    │   Exporter      │    │   Exporter      │
│   Port: 9092    │    │   Port: 8000    │    │   Port: 8001    │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
                    ┌─────────────────┐
                    │   Prometheus    │
                    │   Port: 9090    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Grafana     │
                    │   Port: 3000    │
                    └─────────────────┘
```

## 🚀 Quick Start

### 1. Start Monitoring Stack

```bash
cd monitoring
./deploy-monitoring.sh start
```

### 2. Access Monitoring Tools

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Airflow Exporter**: http://localhost:9092/metrics

### 3. Import Dashboards

Grafana will automatically load the pre-configured dashboards.

## 📊 Available Dashboards

### **Airflow Monitoring Dashboard**

- **DAG Status Count** - Real-time DAG execution status
- **Task Status Count** - Task execution metrics
- **Task Duration** - Performance monitoring
- **DAG Processing Duration** - Pipeline efficiency
- **Scheduler Heartbeat** - Scheduler health
- **Pool Open Slots** - Resource utilization

### **Crypto Pipeline Dashboard** (Existing)

- **Data Flow Metrics** - Producer/Consumer throughput
- **Database Performance** - PostgreSQL metrics
- **Kafka/Redpanda Metrics** - Message queue health

## 🔍 Key Metrics

### **Airflow Metrics**

```promql
# DAG Status
airflow_dag_status_count

# Task Status
airflow_task_status_count

# Performance
airflow_task_duration_seconds
airflow_dag_processing_duration_seconds

# Health
airflow_scheduler_heartbeat
airflow_pool_open_slots
```

### **Pipeline Metrics**

```promql
# Data Throughput
rate(producer_messages_total[5m])
rate(consumer_messages_total[5m])

# Database Performance
postgres_up
postgres_exporter_scrapes_total

# Kafka/Redpanda
kafka_brokers
kafka_consumer_lag
```

## 🛠️ Management Commands

### **Monitoring Stack**

```bash
# Start monitoring
./deploy-monitoring.sh start

# Check status
./deploy-monitoring.sh status

# View logs
./deploy-monitoring.sh logs

# Restart services
./deploy-monitoring.sh restart

# Stop monitoring
./deploy-monitoring.sh stop
```

### **Individual Services**

```bash
# Prometheus logs
docker-compose -f docker-compose.monitoring.yml logs prometheus

# Grafana logs
docker-compose -f docker-compose.monitoring.yml logs grafana

# Airflow exporter logs
docker-compose -f docker-compose.monitoring.yml logs airflow-exporter
```

## 🔧 Configuration

### **Prometheus Configuration**

Located at: `monitoring/prometheus/prometheus.yml`

**Key Settings:**

- **Scrape Interval**: 15s (global), 30s (Airflow)
- **Retention**: Default (15 days)
- **Targets**: All pipeline components

### **Grafana Configuration**

Located at: `monitoring/grafana/`

**Features:**

- **Auto-provisioning** of dashboards
- **Prometheus datasource** pre-configured
- **Refresh rate**: 5s for real-time monitoring

### **Airflow Exporter Configuration**

Located at: `monitoring/docker-compose.monitoring.yml`

**Environment Variables:**

```yaml
AIRFLOW__WEBSERVER__BASE_URL: "http://airflow-webserver:8080"
AIRFLOW__WEBSERVER__RBAC: "true"
AIRFLOW__WEBSERVER__AUTH_BACKEND: "airflow.auth.backend.basic_auth"
AIRFLOW__WEBSERVER__AUTHENTICATE: "true"
AIRFLOW__WEBSERVER__AUTH_USERNAME: "admin"
AIRFLOW__WEBSERVER__AUTH_PASSWORD: "admin123"
```

## 📈 Dashboard Customization

### **Adding New Panels**

1. Open Grafana at http://localhost:3000
2. Navigate to the Airflow dashboard
3. Click "Add Panel" or edit existing panels
4. Use PromQL queries to create new visualizations

### **Creating Custom Dashboards**

1. Create new dashboard in Grafana
2. Add Prometheus as datasource
3. Create panels with relevant metrics
4. Export as JSON for version control

### **Useful PromQL Queries**

```promql
# DAG Success Rate
rate(airflow_dag_status_count{status="success"}[5m]) /
rate(airflow_dag_status_count[5m])

# Task Failure Rate
rate(airflow_task_status_count{status="failed"}[5m]) /
rate(airflow_task_status_count[5m])

# Average Task Duration
avg(airflow_task_duration_seconds)

# Pipeline Throughput
rate(producer_messages_total[5m])
```

## 🚨 Alerting & Notifications

### **Setting Up Alerts**

1. **Grafana Alerts**:

   - Navigate to Alerting in Grafana
   - Create alert rules for critical metrics
   - Configure notification channels (email, Slack, etc.)

2. **Prometheus Alerting**:
   - Configure alertmanager
   - Define alert rules
   - Set up notification policies

### **Recommended Alerts**

- **DAG Failures**: Alert when DAGs fail consecutively
- **Task Timeouts**: Alert for long-running tasks
- **Scheduler Issues**: Alert when scheduler heartbeat stops
- **Pipeline Delays**: Alert for data processing delays
- **Resource Exhaustion**: Alert for low pool slots

## 🔍 Troubleshooting

### **Common Issues**

#### **1. Airflow Exporter Not Accessible**

```bash
# Check if Airflow is running
docker ps | grep airflow-webserver

# Check exporter logs
docker-compose -f docker-compose.monitoring.yml logs airflow-exporter

# Verify network connectivity
docker network inspect crypto-network
```

#### **2. Prometheus Targets Down**

```bash
# Check target status
curl http://localhost:9090/api/v1/targets

# Verify service endpoints
curl http://localhost:9092/metrics  # Airflow
curl http://localhost:9187/metrics  # PostgreSQL
curl http://localhost:9308/metrics  # Kafka
```

#### **3. Grafana Dashboard Issues**

```bash
# Check datasource configuration
# Verify Prometheus is accessible from Grafana
# Check dashboard JSON syntax
```

### **Debug Commands**

```bash
# Check all service statuses
./deploy-monitoring.sh status

# View real-time logs
./deploy-monitoring.sh logs

# Test individual endpoints
curl -s http://localhost:9092/metrics | head -20
curl -s http://localhost:9090/api/v1/targets | jq .
```

## 📚 Advanced Features

### **Custom Metrics**

- **Business Metrics**: Add custom counters for business logic
- **Performance Metrics**: Track specific pipeline bottlenecks
- **Quality Metrics**: Monitor data quality indicators

### **Integration Options**

- **Slack Notifications**: Configure Slack webhooks for alerts
- **Email Alerts**: Set up SMTP for email notifications
- **External Monitoring**: Integrate with external monitoring tools

### **Scaling Considerations**

- **High Availability**: Run multiple Prometheus instances
- **Data Retention**: Configure long-term storage
- **Performance**: Optimize scrape intervals and retention

## 🔒 Security Considerations

### **Access Control**

- **Grafana Authentication**: Use strong passwords
- **Network Security**: Limit access to monitoring ports
- **Data Protection**: Secure sensitive metrics

### **Best Practices**

- **Regular Updates**: Keep monitoring tools updated
- **Backup Configuration**: Version control all configs
- **Monitoring the Monitor**: Monitor monitoring stack health

## 📖 Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Airflow Monitoring](https://airflow.apache.org/docs/apache-airflow/stable/logging-monitoring/metrics.html)
- [PromQL Query Examples](https://prometheus.io/docs/prometheus/latest/querying/examples/)

---

**🎯 Remember: Good monitoring leads to better observability, which leads to faster problem resolution and improved system reliability!**
