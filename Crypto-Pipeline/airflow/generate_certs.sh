#!/bin/bash

# Generate SSL certificates for Airflow HTTPS
# This script creates self-signed certificates for development/testing
# For production, use proper CA-signed certificates

set -e

# SECURITY WARNING: This script generates sensitive files
# NEVER commit these files to version control
# The .gitignore file should exclude all certificate files

CERT_DIR="certs"
CERT_FILE="airflow.crt"
KEY_FILE="airflow.key"
PEM_FILE="airflow.pem"

echo "🔐 Generating SSL certificates for Airflow HTTPS..."
echo "⚠️  SECURITY WARNING: These files contain sensitive information!"
echo "   - NEVER commit them to version control"
echo "   - Store them securely and restrict access"
echo "   - Use proper CA-signed certificates in production"
echo ""

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate private key with strong encryption
echo "📝 Generating private key (2048-bit RSA)..."
openssl genrsa -out "$CERT_DIR/$KEY_FILE" 2048

# Generate certificate signing request
echo "📝 Generating certificate signing request..."
openssl req -new -key "$CERT_DIR/$KEY_FILE" -out "$CERT_DIR/airflow.csr" -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=localhost"

# Generate self-signed certificate
echo "📝 Generating self-signed certificate..."
openssl x509 -req -days 365 -in "$CERT_DIR/airflow.csr" -signkey "$CERT_DIR/$KEY_FILE" -out "$CERT_DIR/$CERT_FILE"

# Create PEM file (some configurations need this)
echo "📝 Creating PEM file..."
cat "$CERT_DIR/$CERT_FILE" "$CERT_DIR/$KEY_FILE" > "$CERT_DIR/$PEM_FILE"

# Set restrictive permissions (owner read/write only)
echo "🔒 Setting secure file permissions..."
chmod 600 "$CERT_DIR/$KEY_FILE"
chmod 644 "$CERT_DIR/$CERT_FILE"
chmod 600 "$CERT_DIR/$PEM_FILE"

# Clean up CSR file
rm "$CERT_DIR/airflow.csr"

echo "✅ SSL certificates generated successfully!"
echo "📁 Certificate files created in: $CERT_DIR/"
echo "   - Certificate: $CERT_FILE"
echo "   - Private Key: $KEY_FILE"
echo "   - PEM Bundle: $PEM_FILE"
echo ""
echo "🔒 SECURITY REMINDERS:"
echo "   ⚠️  These files are now in $CERT_DIR/"
echo "   ⚠️  NEVER commit them to version control"
echo "   ⚠️  Keep them secure and restrict access"
echo "   ⚠️  For production, use proper CA-signed certificates"
echo ""
echo "📋 Next steps:"
echo "   1. Verify files are NOT tracked by git: git status"
echo "   2. Restart Airflow to use HTTPS"
echo "   3. Access Airflow at: https://localhost:8443"
echo "   4. Accept the self-signed certificate warning in your browser"
echo ""
echo "🔍 To verify git status, run: git status"
