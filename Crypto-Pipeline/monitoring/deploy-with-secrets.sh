#!/bin/bash

# Deploy Periodic Email Service with Docker Secrets (Most Secure Method)

set -e

echo "🔐 Deploying with Docker Secrets (Most Secure Method)"
echo "=" * 60

# Check if secret already exists
if docker secret ls | grep -q "smtp_password"; then
    echo "✅ Docker secret 'smtp_password' already exists"
    echo "💡 To update the password, remove and recreate the secret:"
    echo "   docker secret rm smtp_password"
    echo "   echo 'new_password' | docker secret create smtp_password -"
    echo ""
else
    echo "🔐 Creating Docker secret 'smtp_password'..."
    echo "📧 Please enter your AUCEgypt app password:"
    read -s password

    if [ -z "$password" ]; then
        echo "❌ No password provided. Exiting."
        exit 1
    fi

    # Create the secret
    echo "$password" | docker secret create smtp_password -
    echo "✅ Docker secret created successfully"
    echo ""
fi

# Build the Docker image
echo "📦 Building Docker image..."
docker build -f Dockerfile.periodic-email -t crypto-pipeline-periodic-email:latest .

# Stop and remove existing container if it exists
echo "🔄 Stopping existing container..."
docker stop periodic-email-service 2>/dev/null || true
docker rm periodic-email-service 2>/dev/null || true

# Deploy with Docker secret
echo "🚀 Deploying with Docker secret..."
docker run -d \
    --name periodic-email-service \
    --network crypto-network \
    --secret smtp_password \
    --env SMTP_PASSWORD_FILE=/run/secrets/smtp_password \
    --restart unless-stopped \
    crypto-pipeline-periodic-email:latest

echo ""
echo "✅ Periodic Email Service deployed successfully with Docker secrets!"
echo "📧 Service will send emails every 5 minutes from hassan.houta@aucegypt.edu to hassan.houta@outlook.com"
echo ""
echo "🔍 Check logs with: docker logs periodic-email-service"
echo "⏹️  Stop service with: docker stop periodic-email-service"
echo ""
echo "🔐 Docker Secret Management:"
echo "   List secrets: docker secret ls"
echo "   Remove secret: docker secret rm smtp_password"
echo "   Update secret: Remove old one and create new one"
echo ""
echo "🧪 Test the service:"
echo "   docker exec periodic-email-service python -c \"from periodic_email_service import PeriodicEmailService; s=PeriodicEmailService(); print('Password configured:', bool(s.smtp_password))\""
