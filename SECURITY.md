# 🔒 Security Documentation

<div align="center">

**Comprehensive security guide for FinSight API**

[Overview](#-overview) • [Threats & Mitigations](#-threats--mitigations) • [Configuration](#-configuration) • [Best Practices](#-best-practices)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Security Architecture](#-security-architecture)
- [Threats & Mitigations](#-threats--mitigations)
- [Configuration](#-configuration)
- [Encryption](#-encryption)
- [Best Practices](#-best-practices)
- [Incident Response](#-incident-response)
- [Compliance](#-compliance)
- [References](#-references)

---

## 🎯 Overview

FinSight API implements **enterprise-grade security measures** to protect sensitive financial data and API credentials. This document outlines the security architecture, threats addressed, and best practices for secure deployment.

### Security Principles

- 🔐 **Defense in Depth**: Multiple layers of security
- 🔐 **Least Privilege**: Minimum necessary permissions
- 🔐 **Encryption at Rest**: Sensitive data encrypted in database
- 🔐 **Encryption in Transit**: HTTPS/TLS for all communications
- 🔐 **Secure by Default**: Security built into architecture

---

## 🏗️ Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│              (HTTPS/TLS Encrypted)                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Application                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Input Validation (Pydantic)                    │   │
│  │  Rate Limiting (TODO)                          │   │
│  │  CORS Protection                                │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Security Service Layer                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │  AES-256 Encryption (Fernet)                   │   │
│  │  Credential Masking                            │   │
│  │  Format Validation                             │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Encrypted Credentials Table                    │   │
│  │  SSL/TLS Connection                            │   │
│  │  Access Control                                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## ⚠️ Threats & Mitigations

### 1. Credential Storage

#### Threat

**Risk Level**: 🔴 **CRITICAL**

- API keys stored in plain text
- Database compromise exposes all credentials
- Single point of failure

#### Mitigation

**Status**: ✅ **IMPLEMENTED**

- **AES-256 Encryption**: All credentials encrypted before storage
- **Separate Table**: `encrypted_credentials` table isolated from config
- **Environment Key**: Encryption key stored in environment variable
- **Key Derivation**: PBKDF2 with 100,000 iterations

**Implementation:**
```python
# Secure storage
db.save_encrypted_credential(
    exchange="binance",
    credential_type="api_key",
    plaintext_value="sk_live_abc123..."
)
# Stored as: "gAAAAABh..." (encrypted)
```

**Security Level**: 🔒 **HIGH** - Industry-standard encryption

---

### 2. Data Transmission

#### Threat

**Risk Level**: 🔴 **CRITICAL**

- Man-in-the-Middle attacks
- Eavesdropping on API communications
- Credential interception

#### Mitigation

**Status**: ✅ **IMPLEMENTED** (Production)

- **HTTPS/TLS**: All communications encrypted in transit
- **SSL Required**: Database connections use SSL
- **Certificate Validation**: Proper certificate chain validation

**Configuration:**
```bash
# Database connection
DATABASE_URL=postgresql://...?sslmode=require

# API served over HTTPS (automatic on Render)
```

**Security Level**: 🔒 **HIGH** - TLS 1.2+ encryption

---

### 3. Database Access

#### Threat

**Risk Level**: 🟡 **HIGH**

- Unauthorized database access
- SQL injection attacks
- Privilege escalation

#### Mitigation

**Status**: ✅ **IMPLEMENTED**

- **Parameterized Queries**: All queries use parameter binding
- **Connection Pooling**: Isolated connection management
- **Least Privilege**: Database user with minimal permissions
- **Encryption at Rest**: Sensitive data encrypted in database

**Best Practices:**
- Use managed database (Neon) with automatic backups
- Enable database audit logs
- Regular security updates
- IP whitelisting (if possible)

**Security Level**: 🔒 **MEDIUM-HIGH** - Multiple layers of protection

---

### 4. Logging & Debugging

#### Threat

**Risk Level**: 🟡 **MEDIUM**

- Sensitive data in logs
- Stack traces exposing internals
- Credential leakage in error messages

#### Mitigation

**Status**: ✅ **IMPLEMENTED**

- **Data Masking**: Sensitive values masked in logs
- **Log Levels**: Appropriate logging levels in production
- **Error Sanitization**: Errors don't expose sensitive info

**Example:**
```python
# Before masking
logger.info(f"API Key: {api_key}")  # ❌ Exposes key

# After masking
logger.info(f"API Key: {security.mask_sensitive_data(api_key)}")  
# ✅ Shows: "sk_l...tkey"
```

**Security Level**: 🔒 **MEDIUM** - Prevents accidental exposure

---

### 5. API Key Permissions

#### Threat

**Risk Level**: 🟡 **HIGH**

- API keys with excessive permissions
- Unauthorized trading operations
- Withdrawal capabilities

#### Mitigation

**Status**: ⚠️ **RECOMMENDED** (Not yet implemented)

**Recommendations:**
- ✅ Validate API key permissions before acceptance
- ✅ Only accept read-only or trading-only keys
- ✅ Reject keys with withdrawal permissions
- ✅ Implement IP whitelisting at exchange level

**TODO Implementation:**
```python
def validate_api_key_permissions(exchange, api_key):
    """Validate API key has minimal required permissions."""
    # Check permissions with exchange API
    # Reject if withdrawal enabled
    # Reject if admin permissions
    pass
```

**Security Level**: 🔒 **PLANNED** - High priority enhancement

---

### 6. Rate Limiting & DDoS

#### Threat

**Risk Level**: 🟡 **MEDIUM**

- Brute force attacks
- API abuse
- Denial of Service

#### Mitigation

**Status**: ⚠️ **RECOMMENDED** (Not yet implemented)

**Recommendations:**
- ✅ Implement rate limiting per IP
- ✅ Limit connection attempts
- ✅ CAPTCHA after failed attempts
- ✅ Use CDN/WAF for DDoS protection

**TODO Implementation:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/exchange/connect")
@limiter.limit("5/minute")
async def connect_exchange(...):
    pass
```

**Security Level**: 🔒 **PLANNED** - Medium priority enhancement

---

### 7. API Authentication

#### Threat

**Risk Level**: 🟡 **MEDIUM**

- Unauthorized API access
- No user identification
- No access control

#### Mitigation

**Status**: ⚠️ **RECOMMENDED** (Not yet implemented)

**Recommendations:**
- ✅ Implement JWT authentication
- ✅ Multi-user support
- ✅ Role-based access control (RBAC)
- ✅ API key authentication for programmatic access

**TODO Implementation:**
```python
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

security = HTTPBearer()

@app.post("/api/analyze")
async def analyze_portfolio(
    token: str = Depends(security),
    ...
):
    # Verify JWT token
    # Check user permissions
    pass
```

**Security Level**: 🔒 **PLANNED** - Medium priority enhancement

---

## ⚙️ Configuration

### Environment Variables

#### Required Variables

| Variable | Purpose | Security Level |
|----------|---------|----------------|
| `ENCRYPTION_KEY` | AES-256 encryption key | 🔴 **CRITICAL** |
| `DATABASE_URL` | Database credentials | 🔴 **CRITICAL** |
| `GROQ_API_KEY` | AI service API key | 🟡 **HIGH** |

#### Variable Security

**✅ DO:**
- Store in environment variables
- Use secrets management (Render, AWS Secrets Manager)
- Rotate regularly
- Use different keys per environment

**❌ DON'T:**
- Commit to Git
- Hardcode in source
- Share via insecure channels
- Reuse across projects

### Encryption Key Management

#### Generating Encryption Key

```bash
python3 -c "from app.services.security import SecurityService; print(SecurityService.generate_encryption_key())"
```

**Output:**
```
qBvcrBrYC9s2T6_UrDBOQPlcb7Es4R4V4WK303zAUks=
```

#### Key Requirements

- **Length**: Minimum 32 characters
- **Uniqueness**: One key per deployment
- **Secrecy**: Never share or commit
- **Rotation**: Rotate every 90 days (recommended)

#### Key Storage

```bash
# Development (.env file - gitignored)
ENCRYPTION_KEY=your-dev-key-here

# Production (Render Environment Variables)
ENCRYPTION_KEY=your-prod-key-here  # Different from dev!
```

---

## 🔐 Encryption

### Encryption Algorithm

**Algorithm**: AES-256 (Advanced Encryption Standard)
**Mode**: Fernet (symmetric encryption)
**Key Derivation**: PBKDF2-HMAC-SHA256
**Iterations**: 100,000

### Encryption Flow

```
Plaintext Credential
        │
        ▼
┌───────────────────┐
│  Format Validation│
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Key Derivation   │
│  (PBKDF2)         │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  AES-256 Encrypt  │
│  (Fernet)         │
└─────────┬─────────┘
          │
          ▼
Encrypted Credential (stored in DB)
```

### Decryption Flow

```
Encrypted Credential (from DB)
        │
        ▼
┌───────────────────┐
│  Key Derivation   │
│  (PBKDF2)         │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  AES-256 Decrypt  │
│  (Fernet)         │
└─────────┬─────────┘
          │
          ▼
Plaintext Credential (in memory only)
```

### Security Properties

- ✅ **Confidentiality**: Encrypted data unreadable without key
- ✅ **Integrity**: Tampering detectable
- ✅ **Authenticity**: Verified encryption source
- ✅ **Forward Secrecy**: Key rotation doesn't affect old data

---

## ✅ Best Practices

### Development

1. **Never commit secrets**
   ```bash
   # .gitignore
   .env
   .env.local
   *.key
   ```

2. **Use environment variables**
   ```python
   import os
   api_key = os.getenv("API_KEY")  # ✅ Good
   api_key = "hardcoded_key"       # ❌ Bad
   ```

3. **Validate inputs**
   ```python
   from pydantic import BaseModel, validator
   
   class Connection(BaseModel):
       api_key: str
       
       @validator('api_key')
       def validate_key(cls, v):
           if len(v) < 20:
               raise ValueError('Invalid API key')
           return v
   ```

4. **Mask sensitive data in logs**
   ```python
   logger.info(f"Connecting with key: {mask_sensitive_data(key)}")
   ```

### Production

1. **HTTPS Only**
   - Enforce HTTPS redirects
   - Use HSTS headers
   - Valid SSL certificates

2. **Database Security**
   - SSL/TLS connections (`sslmode=require`)
   - Strong passwords
   - Regular backups
   - Access logging

3. **Key Rotation**
   - Rotate encryption keys quarterly
   - Rotate API keys monthly
   - Document rotation process

4. **Monitoring**
   - Monitor failed login attempts
   - Alert on suspicious activity
   - Regular security audits

5. **Updates**
   - Keep dependencies updated
   - Apply security patches promptly
   - Monitor CVE databases

---

## 🚨 Incident Response

### Security Incident Procedure

#### 1. Immediate Response

1. **Isolate**: Disable affected services/accounts
2. **Assess**: Determine scope of compromise
3. **Contain**: Prevent further damage
4. **Document**: Record all actions taken

#### 2. Credential Compromise

**If API keys are compromised:**

1. **Revoke Immediately**
   ```bash
   # Revoke at exchange
   - Binance: Account → API Management → Delete
   - Alpaca: Dashboard → API Keys → Revoke
   ```

2. **Generate New Encryption Key**
   ```bash
   python3 -c "from app.services.security import SecurityService; print(SecurityService.generate_encryption_key())"
   ```

3. **Re-encrypt All Credentials**
   - Update `ENCRYPTION_KEY` in environment
   - Re-encrypt all stored credentials
   - Verify encryption successful

4. **Audit Logs**
   - Review access logs
   - Identify unauthorized access
   - Document findings

5. **Notify Users**
   - Inform affected users
   - Provide remediation steps
   - Update security documentation

#### 3. Database Compromise

**If database is compromised:**

1. **Isolate Database**
   - Disable public access
   - Change credentials
   - Enable additional logging

2. **Assess Damage**
   - Check what data was accessed
   - Identify affected users
   - Review access logs

3. **Remediate**
   - Restore from backup (if needed)
   - Rotate all credentials
   - Update security measures

4. **Post-Incident**
   - Root cause analysis
   - Update security procedures
   - Additional monitoring

---

## 📋 Security Checklist

### Pre-Deployment

- [ ] ✅ All secrets in environment variables
- [ ] ✅ `ENCRYPTION_KEY` generated and secure
- [ ] ✅ HTTPS configured (automatic on Render)
- [ ] ✅ Database SSL enabled (`sslmode=require`)
- [ ] ✅ CORS configured correctly
- [ ] ✅ Input validation on all endpoints
- [ ] ✅ Error messages sanitized
- [ ] ✅ Logs don't expose sensitive data

### Post-Deployment

- [ ] ✅ Health checks configured
- [ ] ✅ Monitoring enabled
- [ ] ✅ Alerts configured
- [ ] ✅ Backup strategy in place
- [ ] ✅ Access logs reviewed
- [ ] ✅ Security updates scheduled

### Ongoing

- [ ] ⚠️ Rate limiting implemented
- [ ] ⚠️ JWT authentication implemented
- [ ] ⚠️ API key permission validation
- [ ] ⚠️ IP whitelisting configured
- [ ] ⚠️ Regular security audits
- [ ] ⚠️ Dependency updates
- [ ] ⚠️ Key rotation schedule

---

## 📚 Compliance

### Data Protection

- **Encryption**: AES-256 for data at rest
- **TLS**: 1.2+ for data in transit
- **Access Control**: Least privilege principle
- **Audit Logging**: All access logged

### Financial Data

- **PCI DSS**: Not applicable (no card data)
- **SOC 2**: Follow best practices
- **GDPR**: Data minimization, encryption

### Recommendations

- Regular security audits
- Penetration testing (annual)
- Compliance reviews
- Documentation updates

---

## 📖 References

### Standards & Frameworks

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Cryptography

- [Cryptography.io Documentation](https://cryptography.io/en/latest/)
- [Fernet Specification](https://github.com/fernet/spec)
- [PBKDF2 RFC 2898](https://tools.ietf.org/html/rfc2898)

### Best Practices

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/secrets.html)
- [12 Factor App](https://12factor.net/config)

---

<div align="center">

**Security is a process, not a product** 🔒

[⬆ Back to Top](#-security-documentation)

</div>
