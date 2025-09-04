history | grep -i revise###################################################################################################
#  Version History
###################################################################################################
#  	Version 	| Date        	         | 	    Author			  |	Comments
#  	1.0      	| 16 AUG, 2025 	         | 	    HASSAN HOUTA	|	Initial.
###################################################################################################
# Airflow Orchestration for Crypto Pipeline
# This directory contains Apache Airflow DAGs and configuration for orchestrating the crypto data pipeline.
###################################################################################################
## Overview

Apache Airflow is used to:
- Schedule and monitor producer/consumer tasks
- Run data quality checks
- Execute DBT transformations
- Manage service health and restarts
- Generate data quality reports

## DAGs

### 1. `crypto_pipeline_dag.py`
- **Schedule**: Every 15 minutes
- **Purpose**: Batch processing of crypto data
- **Tasks**:
  - Health checks for Kafka and PostgreSQL
  - Run producer for 5 minutes
  - Run consumer for 5 minutes
  - Validate data quality

### 2. `crypto_streaming_dag.py`
- **Schedule**: Hourly
- **Purpose**: Monitor and manage streaming services
- **Tasks**:
  - Check producer/consumer status
  - Monitor service health
  - Restart unhealthy services
  - Track pipeline metrics

### 3. `crypto_dbt_dag.py`
- **Schedule**: Every 30 minutes
- **Purpose**: Run DBT transformations
- **Tasks**:
  - Check source data freshness
  - Run DBT models
  - Execute DBT tests
  - Generate data quality reports

## Setup

### 1. Initialize Airflow

```bash
# Set up environment
export AIRFLOW_UID=$(id -u)

# Initialize Airflow database
make airflow-init

# Start Airflow services
make airflow-start

### Start Full Stack

# Start all services including Airflow
make stack-start

### Stop Full Stack
```bash
# Stop all services
make stack-stop
```

### View Logs
```bash
# View Airflow logs
make airflow-logs
```

### 2. Access Airflow UI

Open http://localhost:8081 in your browser:
- Username: `admin`
- Password: `admin123`

### 3. Configure Connections

In Airflow UI, go to Admin > Connections and add:

#### Kafka Connection
- Connection Id: `kafka_default`
- Connection Type: `Generic`
- Host: `redpanda`
- Port: `9092`

#### PostgreSQL Connection
- Connection Id: `postgres_crypto`
- Connection Type: `Postgres`
- Host: `postgres`
- Schema: `crypto_db`
- Login: `crypto_user`
- Password: `cryptopass123`
- Port: `5432`

## Usage



# View specific DAG logs in UI
# Go to DAGs > [DAG Name] > Graph > [Task] > Logs
```

### Trigger DAGs Manually

In the Airflow UI:
1. Navigate to DAGs page
2. Toggle the DAG to "On" state
3. Click the play button to trigger manually

Or via CLI:
```bash
docker exec -it airflow-airflow-webserver-1 airflow dags trigger crypto_pipeline
```

## DAG Configuration

### Environment Variables

Set in `docker-compose-airflow.yml`:
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address
- `POSTGRES_HOST`: PostgreSQL host
- `POSTGRES_DATABASE`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password

### Schedule Intervals

Modify in DAG files:
- `schedule_interval='@hourly'`: Run every hour
- `schedule_interval='*/15 * * * *'`: Run every 15 minutes
- `schedule_interval=timedelta(minutes=30)`: Run every 30 minutes

## Monitoring

### Pipeline Metrics
The streaming DAG monitors:
- Message throughput
- Data lag (time since last message)
- Data gaps
- Service health

### Data Quality
The DBT DAG validates:
- Data freshness
- Completeness
- Anomalies (negative prices, invalid OHLCV)
- Missing time periods

### Alerts
Configure email alerts in `airflow.cfg` or DAG default_args:
```python
default_args = {
    'email': ['hassan.houta@outlook.com'],
    'email_on_failure': True,
    'email_on_retry': True,
}
```

## Troubleshooting

### Common Issues

1. **DAG not appearing in UI**
   - Check for syntax errors: `python airflow/dags/your_dag.py`
   - Refresh DAGs in UI
   - Check scheduler logs

2. **Task failures**
   - Check task logs in UI
   - Verify service connectivity
   - Check resource availability

3. **Slow performance**
   - Increase parallelism in airflow.cfg
   - Add more scheduler instances
   - Optimize DAG structure

### Useful Commands

```bash
# Test DAG syntax
docker exec -it airflow-airflow-webserver-1 python /opt/airflow/dags/crypto_pipeline_dag.py

# List DAGs
docker exec -it airflow-airflow-webserver-1 airflow dags list

# Test specific task
docker exec -it airflow-airflow-webserver-1 airflow tasks test crypto_pipeline check_kafka_health 2024-01-01

# Clear task instances
docker exec -it airflow-airflow-webserver-1 airflow tasks clear crypto_pipeline
```

## Best Practices

1. **Idempotency**: Ensure tasks can be safely re-run
2. **Timeouts**: Set appropriate task timeouts
3. **Retries**: Configure retry logic for transient failures
4. **Dependencies**: Use proper task dependencies
5. **Resource Management**: Monitor CPU/memory usage
6. **Logging**: Use structured logging for debugging
7. **Testing**: Test DAGs locally before deployment

## Architecture

```
┌─────────────────┐
│   Airflow       │
│   Scheduler     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│   Producer      │────▶│    Redpanda     │
│   (Coinbase)    │     │    (Kafka)      │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Consumer      │
                        │   (PostgreSQL)  │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │      DBT        │
                        │ Transformations │
                        └─────────────────┘
```

## Future Enhancements

- Add Slack/PagerDuty notifications
- Implement auto-scaling based on load
- Add data lineage tracking
- Create custom Airflow operators
- Add ML model training DAGs
- Implement data archival strategies

## 🔐 Security & Deployment

### Security Overview

This Airflow deployment includes comprehensive security measures to protect your data pipeline in both development and production environments.

### 🚨 Security Issues with HTTP (Default Setup)

**Current vulnerabilities:**
- **Unencrypted traffic** - Data can be intercepted
- **No certificate validation** - Man-in-the-middle attacks possible
- **Credentials transmitted in plain text**
- **No CSRF protection**
- **Limited rate limiting**
- **No security headers**

### ✅ Security Measures Implemented

#### **1. HTTPS/SSL Encryption**
- **SSL/TLS 1.2 and 1.3** with strong ciphers
- **Self-signed certificates** for development (replace with CA-signed for production)
- **HTTP to HTTPS redirect** - No HTTP traffic allowed
- **HSTS headers** - Force HTTPS usage

#### **2. Reverse Proxy (Nginx)**
- **SSL termination** at the proxy level
- **No direct external access** to Airflow webserver
- **Rate limiting** (10 req/s for main app, 30 req/s for API)
- **Security headers** implementation
- **Request filtering** and validation

#### **3. Enhanced Authentication & Authorization**
- **RBAC (Role-Based Access Control)** enabled
- **Session security** with secure cookies
- **Login attempt limiting** (5 attempts, 60s delay)
- **Session timeout** (1 hour)
- **Audit logging** enabled

#### **4. Security Headers**
```http
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'self';
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### 🚀 Deployment Options

#### **Option 1: Secure HTTPS Setup (Recommended for Production)**
```bash
# Deploy with HTTPS and security features
./deploy.sh secure

# Access Airflow at: https://localhost
# Username: admin
# Password: admin123
```

#### **Option 2: Development HTTP Setup (Development Only)**
```bash
# Deploy with HTTP for development
./deploy.sh dev

# Access Airflow at: http://localhost:8081
# Username: admin
# Password: admin123
```

### 🔒 Production Security Checklist

**Before going live:**
- [ ] **Replace self-signed certificates** with CA-signed certificates
- [ ] **Use strong passwords** (12+ chars, mixed case, numbers, symbols)
- [ ] **Implement external authentication** (LDAP, OAuth, SAML)
- [ ] **Enable multi-factor authentication (MFA)**
- [ ] **Set up proper logging** and monitoring
- [ ] **Configure backup and disaster recovery**
- [ ] **Implement network segmentation** and firewall rules
- [ ] **Regular security updates** and patching

### 🛠️ Management Commands

```bash
# Check deployment status
./deploy.sh status

# View logs
./deploy.sh logs

# Restart services
./deploy.sh restart

# Stop all services
./deploy.sh stop

# Show help
./deploy.sh help
```

### 📁 Security Files

- `docker-compose-secure.yml` - Secure HTTPS deployment
- `nginx/nginx.conf` - Nginx configuration with security
- `nginx/conf.d/airflow.conf` - Airflow-specific nginx config
- `generate_certs.sh` - SSL certificate generation
- `deploy.sh` - Easy deployment script
- `SECURITY_GUIDE.md` - Comprehensive security documentation

### 🔍 Security Testing

```bash
# SSL configuration testing
nmap --script ssl-enum-ciphers -p 443 localhost

# Security headers testing
curl -I -k https://localhost

# Vulnerability scanning
docker run --rm -v $(pwd):/app owasp/zap2docker-stable zap-baseline.py -t https://localhost
```

### 📚 Security Resources

- [Airflow Security Documentation](https://airflow.apache.org/docs/apache-airflow/stable/security/index.html)
- [OWASP Security Guidelines](https://owasp.org/www-project-top-ten/)
- [Nginx Security Best Practices](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

**⚠️ Security Reminder: Security is an ongoing process, not a one-time setup!**
