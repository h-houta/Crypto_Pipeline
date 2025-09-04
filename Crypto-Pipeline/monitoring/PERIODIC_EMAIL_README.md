# Periodic Email Service

This service sends status emails every 5 minutes to monitor the health of your Crypto Pipeline system.

## Features

- **Automatic Emails**: Sends status reports every 5 minutes
- **Service Health Monitoring**: Checks all pipeline services (Airflow, Prometheus, Grafana, etc.)
- **Email Configuration**: Uses AUCEgypt SMTP to send emails to Outlook
- **Docker Ready**: Easy deployment with Docker

## Configuration

### 1. Environment Variables

Copy `periodic_email.env` to `.env` and configure:

```bash
# SMTP Configuration for Gmail (Recommended - supports app passwords)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=houtahassan61@gmail.com
SMTP_PASSWORD=your_gmail_app_password_here

# Email Configuration
FROM_EMAIL=houtahassan61@gmail.com
TO_EMAIL=hassan.houta@aucegypt.edu
```

### 2. Gmail App Password

For Gmail, you need to:

1. Enable 2-factor authentication on your Google account
2. Generate an "App Password" specifically for this service
3. Use the app password instead of your regular password
4. Make sure "Less secure app access" is disabled (it's deprecated anyway)

## Deployment

### Quick Deploy

```bash
# Make script executable
chmod +x deploy-periodic-email.sh

# Deploy the service
./deploy-periodic-email.sh
```

### Manual Docker Deployment

```bash
# Build the image
docker build -f Dockerfile.periodic-email -t crypto-pipeline-periodic-email:latest .

# Run the container
docker run -d \
    --name periodic-email-service \
    --network crypto-pipeline-network \
    --restart unless-stopped \
    -e SMTP_PASSWORD=your_password \
    crypto-pipeline-periodic-email:latest
```

## Monitoring

### Check Service Status

```bash
# View logs
docker logs periodic-email-service

# Check container status
docker ps | grep periodic-email

# Health check
docker exec periodic-email-service curl -f http://localhost:8002/health
```

### Stop Service

```bash
docker stop periodic-email-service
docker rm periodic-email-service
```

## Email Format

The service sends emails with:

- **Subject**: `[Crypto Pipeline] Status Report - {timestamp}`
- **Content**:
  - Overall system status
  - Individual service health (🟢 Healthy / 🔴 Down)
  - Timestamp and details
  - Service-specific error messages if any

## Services Monitored

- Airflow (http://airflow:8080/health)
- Prometheus (http://prometheus-standalone:9090/-/healthy)
- Grafana (http://grafana:3000/api/health)
- Producer (http://producer:8000/health)
- Consumer (http://consumer:8001/health)
- PostgreSQL (http://postgres-exporter:9187/metrics)
- Redpanda (http://redpanda:9644/metrics)

## Troubleshooting

### Common Issues

1. **SMTP Authentication Failed**

   - Check your AUCEgypt password/app password
   - Verify SMTP settings

2. **Service Not Starting**

   - Check Docker logs: `docker logs periodic-email-service`
   - Verify network connectivity

3. **Emails Not Sending**

   - Check SMTP configuration
   - Verify firewall/network settings
   - Check AUCEgypt account settings

### Logs

The service logs all activities including:

- Email sending attempts
- Service health checks
- Errors and warnings

## Customization

### Change Email Interval

Modify the `EMAIL_INTERVAL_MINUTES` environment variable or edit the service code.

### Add/Remove Services

Edit the `services` dictionary in `periodic_email_service.py` to monitor different endpoints.

### Email Template

Customize the email format by modifying the `send_status_email` method.
