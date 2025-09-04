# 🔒 Secure Email Service Setup

This guide shows you how to configure the Periodic Email Service **without exposing your password** in plain text.

## 🚨 Security Warning

**NEVER commit passwords to git or share them in plain text!**

## 🔐 Password Configuration Methods (In Order of Security)

### Method 1: Environment Variables (Recommended for Development)

```bash
# Set password in your current shell (not permanent)
export SMTP_PASSWORD="your_aucegypt_password"

# Deploy the service
./deploy-periodic-email.sh
```

**Pros**: Simple, no files created
**Cons**: Password lost when shell closes

### Method 2: Local Environment File (Development)

```bash
# Create a local .env file (NEVER commit this!)
echo "SMTP_PASSWORD=your_aucegypt_password" > .env

# Deploy the service
./deploy-periodic-email.sh
```

**Pros**: Persistent across shell sessions
**Cons**: File exists on disk (ensure it's in .gitignore)

### Method 3: Docker Secrets (Production)

```bash
# Create a Docker secret
echo "your_aucegypt_password" | docker secret create smtp_password -

# Deploy with secret
docker run -d \
    --name periodic-email-service \
    --network crypto-pipeline-network \
    --secret smtp_password \
    --env SMTP_PASSWORD_FILE=/run/secrets/smtp_password \
    crypto-pipeline-periodic-email:latest
```

**Pros**: Most secure, encrypted at rest
**Cons**: More complex setup

### Method 4: Interactive Input (Testing)

```bash
# Deploy without password
./deploy-periodic-email.sh

# Enter password interactively
docker exec -it periodic-email-service python periodic_email_service.py
```

**Pros**: No password stored anywhere
**Cons**: Manual intervention required

## 🛡️ Security Best Practices

### 1. Use App Passwords for AUCEgypt

Instead of your main password:

1. Enable 2-factor authentication on your AUCEgypt account
2. Generate an "App Password" specifically for this service
3. Use the app password instead of your regular password

### 2. Network Security

```bash
# Ensure the service runs on internal network only
docker run --network crypto-pipeline-network \
    --expose 8002 \
    periodic-email-service
```

### 3. File Permissions

```bash
# If using .env file, restrict access
chmod 600 .env
chown $USER:$USER .env
```

### 4. Regular Password Rotation

- Change app passwords regularly
- Monitor for unauthorized access
- Use different passwords for different services

## 🔍 Verification Steps

### 1. Check Service Status

```bash
# View logs
docker logs periodic-email-service

# Check if emails are being sent
docker exec periodic-email-service tail -f /app/email_service.log
```

### 2. Test Email Sending

```bash
# Test the service manually
docker exec -it periodic-email-service python -c "
from periodic_email_service import PeriodicEmailService
service = PeriodicEmailService()
print('Password configured:', bool(service.smtp_password))
"
```

### 3. Monitor Security

```bash
# Check for password exposure in logs
docker logs periodic-email-service | grep -i password

# Verify no sensitive data in container
docker exec periodic-email-service env | grep -i smtp
```

## 🚫 What NOT to Do

❌ **Never commit .env files to git**

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
```

❌ **Never hardcode passwords in scripts**

```bash
# BAD
SMTP_PASSWORD="mypassword123"

# GOOD
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
```

❌ **Never share passwords in logs or output**

```bash
# BAD - password visible
echo "Password: $SMTP_PASSWORD"

# GOOD - password hidden
echo "Password: ${SMTP_PASSWORD:+***}"
```

## 🔧 Troubleshooting

### Password Not Working

```bash
# Check AUCEgypt settings
# 1. Verify SMTP settings: smtp-mail.outlook.com:587
# 2. Enable "Less secure app access" or use App Password
# 3. Check if 2FA is blocking access
```

### Service Won't Start

```bash
# Check logs for password errors
docker logs periodic-email-service

# Verify environment variables
docker exec periodic-email-service env | grep SMTP
```

### Emails Not Sending

```bash
# Test SMTP connection manually
docker exec periodic-email-service python -c "
import smtplib
s = smtplib.SMTP('smtp-mail.outlook.com', 587)
s.starttls()
s.login('hassan.houta@aucegypt.edu', 'your_password')
s.quit()
"
```

## 📋 Quick Start (Most Secure)

```bash
# 1. Set password temporarily
export SMTP_PASSWORD="your_app_password"

# 2. Deploy service
./deploy-periodic-email.sh

# 3. Verify it's working
docker logs periodic-email-service

# 4. Clear password from shell history
history -d $((HISTCMD-1))
```

## 🔐 Advanced: Docker Compose with Secrets

Create `docker-compose.email.yml`:

```yaml
version: "3.8"
services:
  periodic-email:
    build:
      context: .
      dockerfile: Dockerfile.periodic-email
    secrets:
      - smtp_password
    environment:
      - SMTP_PASSWORD_FILE=/run/secrets/smtp_password
    networks:
      - crypto-pipeline-network

secrets:
  smtp_password:
    external: true

networks:
  crypto-pipeline-network:
    external: true
```

Deploy with:

```bash
# Create secret
echo "your_password" | docker secret create smtp_password -

# Deploy
docker-compose -f docker-compose.email.yml up -d
```
