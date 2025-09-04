# 🔐 Airflow Security Guide

## Overview
This guide outlines the security measures implemented in your Airflow deployment and provides best practices for production environments.

## 🚨 Security Issues with HTTP (Current Setup)

### **Vulnerabilities:**
- **Unencrypted traffic** - Data can be intercepted
- **No certificate validation** - Man-in-the-middle attacks possible
- **Credentials transmitted in plain text**
- **No CSRF protection**
- **Limited rate limiting**
- **No security headers**

## ✅ Security Measures Implemented

### **1. HTTPS/SSL Encryption**
- **SSL/TLS 1.2 and 1.3** with strong ciphers
- **Self-signed certificates** for development (replace with CA-signed for production)
- **HTTP to HTTPS redirect** - No HTTP traffic allowed
- **HSTS headers** - Force HTTPS usage

### **2. Reverse Proxy (Nginx)**
- **SSL termination** at the proxy level
- **No direct external access** to Airflow webserver
- **Rate limiting** (10 req/s for main app, 30 req/s for API)
- **Security headers** implementation
- **Request filtering** and validation

### **3. Enhanced Authentication & Authorization**
- **RBAC (Role-Based Access Control)** enabled
- **Session security** with secure cookies
- **Login attempt limiting** (5 attempts, 60s delay)
- **Session timeout** (1 hour)
- **Audit logging** enabled

### **4. Security Headers**
```http
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'self';
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### **5. Network Security**
- **Internal service isolation** - Airflow only accessible via proxy
- **Docker network segmentation**
- **No direct port exposure** for sensitive services

## 🚀 Deployment Options

### **Option 1: Secure HTTPS Setup (Recommended)**
```bash
# Use the secure docker-compose file
docker-compose -f docker-compose-secure.yml up -d

# Access Airflow at: https://localhost
```

### **Option 2: Current HTTP Setup (Development Only)**
```bash
# Use the original docker-compose file
docker-compose -f docker-compose-airflow.yml up -d

# Access Airflow at: http://localhost:8081
```

## 🔒 Production Security Checklist

### **Before Going Live:**
- [ ] **Replace self-signed certificates** with CA-signed certificates
- [ ] **Use strong passwords** (12+ chars, mixed case, numbers, symbols)
- [ ] **Implement external authentication** (LDAP, OAuth, SAML)
- [ ] **Enable multi-factor authentication (MFA)**
- [ ] **Set up proper logging** and monitoring
- [ ] **Configure backup and disaster recovery**
- [ ] **Implement network segmentation** and firewall rules
- [ ] **Regular security updates** and patching

### **SSL Certificate Management:**
```bash
# For production, use Let's Encrypt or commercial CA
# Example with Let's Encrypt:
certbot certonly --standalone -d yourdomain.com

# Update nginx configuration with real certificates
ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
```

### **Environment Variables for Production:**
```bash
# Generate strong Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate strong secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Set in environment or .env file
AIRFLOW__CORE__FERNET_KEY=your_fernet_key_here
AIRFLOW__WEBSERVER__SECRET_KEY=your_secret_key_here
```

## 🛡️ Additional Security Measures

### **1. Database Security**
- **Encrypted connections** to PostgreSQL
- **Strong database passwords**
- **Database access restrictions**

### **2. API Security**
- **Rate limiting** on API endpoints
- **API authentication** required
- **Request validation** and sanitization

### **3. Monitoring & Alerting**
- **Security event logging**
- **Failed login attempt alerts**
- **Unusual access pattern detection**

### **4. Backup Security**
- **Encrypted backups**
- **Secure backup storage**
- **Backup access controls**

## 🚨 Security Incident Response

### **If Compromised:**
1. **Immediately isolate** the affected system
2. **Change all passwords** and keys
3. **Review logs** for unauthorized access
4. **Assess data exposure** and notify stakeholders
5. **Implement additional security measures**
6. **Document incident** and lessons learned

## 📚 Additional Resources

- [Airflow Security Documentation](https://airflow.apache.org/docs/apache-airflow/stable/security/index.html)
- [OWASP Security Guidelines](https://owasp.org/www-project-top-ten/)
- [Nginx Security Best Practices](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

## 🔍 Security Testing

### **Regular Security Audits:**
```bash
# SSL configuration testing
nmap --script ssl-enum-ciphers -p 443 localhost

# Security headers testing
curl -I -k https://localhost

# Vulnerability scanning
docker run --rm -v $(pwd):/app owasp/zap2docker-stable zap-baseline.py -t https://localhost
```

---

**⚠️ Remember: Security is an ongoing process, not a one-time setup!**
