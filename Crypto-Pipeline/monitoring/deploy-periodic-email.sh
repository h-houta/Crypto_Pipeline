#!/bin/bash

# Deploy Periodic Email Service for Crypto Pipeline Monitoring

set -e

echo "🚀 Deploying Periodic Email Service..."

# Check if we have a password
if [ -z "$SMTP_PASSWORD" ]; then
    echo "⚠️  Warning: SMTP_PASSWORD environment variable not set"
    echo "📧 The service will prompt for password on startup or use Docker secrets"
    echo ""
fi

# Build the Docker image
echo "📦 Building Docker image..."
cd monitoring && docker build -f Dockerfile.periodic-email -t crypto-pipeline-periodic-email:latest . && cd ..

# Stop and remove existing container if it exists
echo "🔄 Stopping existing container..."
docker stop periodic-email-service 2>/dev/null || true
docker rm periodic-email-service 2>/dev/null || true

# Determine deployment method
if [ -n "$SMTP_PASSWORD" ]; then
    echo "🔐 Using environment variable for SMTP password"
    docker run -d \
        --name periodic-email-service \
        --network crypto-network \
        --restart unless-stopped \
        -e SMTP_SERVER=${SMTP_SERVER:-smtp.gmail.com} \
        -e SMTP_PORT=${SMTP_PORT:-587} \
        -e SMTP_USER=${SMTP_USER:-houtahassan61@gmail.com} \
        -e SMTP_PASSWORD="$SMTP_PASSWORD" \
        crypto-pipeline-periodic-email:latest
else
    echo "🔐 No password provided - service will prompt on startup"
    echo "💡 To run with password, use one of these methods:"
    echo "   1. Set SMTP_PASSWORD environment variable"
    echo "   2. Use Docker secrets"
    echo "   3. Run interactively"
    echo ""

    # Run without password - service will handle authentication
    docker run -d \
        --name periodic-email-service \
        --network crypto-network \
        --restart unless-stopped \
        -e SMTP_SERVER=${SMTP_SERVER:-smtp.gmail.com} \
        -e SMTP_PORT=${SMTP_PORT:-587} \
        -e SMTP_USER=${SMTP_USER:-houtahassan61@gmail.com} \
        crypto-pipeline-periodic-email:latest
fi

echo ""
echo "✅ Periodic Email Service deployed successfully!"
echo "📧 Service will send emails every 5 minutes from houtahassan61@gmail.com to hassan.houta@aucegypt.edu"
echo ""
echo "🔍 Check logs with: docker logs periodic-email-service"
echo "⏹️  Stop service with: docker stop periodic-email-service"
echo ""
echo "🔐 Password Configuration Options:"
echo "   1. Environment Variable: export SMTP_PASSWORD='your_password'"
echo "   2. Docker Secret: echo 'password' | docker secret create smtp_password -"
echo "   3. Interactive: docker exec -it periodic-email-service python periodic_email_service.py"
