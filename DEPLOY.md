# 🚀 Deployment Guide - Render.com

<div align="center">

**Complete guide for deploying FinSight API to Render.com**

[Prerequisites](#-prerequisites) • [Quick Deploy](#-quick-deploy) • [Configuration](#-configuration) • [Troubleshooting](#-troubleshooting)

</div>

---

## 📋 Table of Contents

- [Prerequisites](#-prerequisites)
- [Quick Deploy](#-quick-deploy)
- [Step-by-Step Guide](#-step-by-step-guide)
- [Configuration](#-configuration)
- [Environment Variables](#-environment-variables)
- [Monitoring & Logs](#-monitoring--logs)
- [Troubleshooting](#-troubleshooting)
- [Performance Optimization](#-performance-optimization)
- [Security Checklist](#-security-checklist)

---

## ✅ Prerequisites

Before deploying, ensure you have:

- ✅ [Render.com account](https://render.com) (Free tier available)
- ✅ Git repository (GitHub, GitLab, or Bitbucket)
- ✅ PostgreSQL database ([Neon](https://neon.tech) recommended)
- ✅ Groq API key ([Get one here](https://console.groq.com))

---

## ⚡ Quick Deploy

### Option 1: Using render.yaml (Recommended)

1. **Push code to Git repository**
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Connect to Render**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click **"New +"** → **"Blueprint"**
   - Connect your Git repository
   - Render will detect `render.yaml` automatically

3. **Configure Environment Variables**
   - Add required variables in Render Dashboard
   - See [Environment Variables](#-environment-variables) section

4. **Deploy**
   - Click **"Apply"**
   - Render will build and deploy automatically

### Option 2: Manual Configuration

Follow the [Step-by-Step Guide](#-step-by-step-guide) below.

---

## 📖 Step-by-Step Guide

### Step 1: Prepare Repository

Ensure all files are committed and pushed:

```bash
# Check status
git status

# Add all files
git add .

# Commit
git commit -m "Prepare for Render deployment"

# Push to remote
git push origin main
```

### Step 2: Create Web Service

1. **Access Render Dashboard**
   - Navigate to [dashboard.render.com](https://dashboard.render.com)
   - Sign in or create account

2. **Create New Web Service**
   - Click **"New +"** button
   - Select **"Web Service"**

3. **Connect Repository**
   - Choose your Git provider (GitHub/GitLab/Bitbucket)
   - Authorize Render access
   - Select your repository
   - Select branch (usually `main`)

### Step 3: Configure Service

#### Basic Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Name** | `finsight-api` | Service name (your choice) |
| **Region** | `Oregon (US West)` | Choose closest to users |
| **Branch** | `main` | Git branch to deploy |
| **Runtime** | `Python 3` | Language runtime |
| **Root Directory** | `.` | Leave default |

#### Build & Start Commands

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**⚠️ Important**: Always use `$PORT` environment variable in start command.

#### Advanced Settings

| Setting | Value | Description |
|---------|-------|-------------|
| **Health Check Path** | `/api/health` | Health check endpoint |
| **Auto-Deploy** | `Yes` | Deploy on git push |
| **Pull Request Previews** | `Yes` (optional) | Preview PR deployments |

### Step 4: Configure Environment Variables

Navigate to **"Environment"** tab and add:

#### Required Variables

```bash
# Database Connection
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# Groq API Key
GROQ_API_KEY=gsk_your_groq_api_key_here

# Encryption Key (CRITICAL - Generate new!)
ENCRYPTION_KEY=your-super-secret-encryption-key-minimum-32-characters
```

#### Optional Variables

```bash
# Python Version
PYTHON_VERSION=3.11.0

# Logging Level
LOG_LEVEL=INFO

# Timezone
TZ=UTC
```

**🔐 Generate Encryption Key:**
```bash
python3 -c "from app.services.security import SecurityService; print(SecurityService.generate_encryption_key())"
```

**⚠️ Security Note**: Never commit these values to Git. Always use Render's environment variable interface.

### Step 5: Deploy

1. **Review Configuration**
   - Double-check all settings
   - Verify environment variables

2. **Create Web Service**
   - Click **"Create Web Service"**
   - Render will start building

3. **Monitor Build**
   - Watch build logs in real-time
   - Build typically takes 5-10 minutes
   - First build may take longer

4. **Verify Deployment**
   - Wait for "Live" status
   - Test health endpoint:
     ```bash
     curl https://groq-finance-inference.onrender.com/api/health
     ```

---

## ⚙️ Configuration

### render.yaml

The project includes a `render.yaml` file for Infrastructure as Code:

```yaml
services:
  - type: web
    name: finsight-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
    healthCheckPath: /api/health
    autoDeploy: true
```

**Using render.yaml:**
- Select **"Blueprint"** instead of **"Web Service"**
- Render detects and applies configuration automatically
- Still need to configure environment variables manually

### Health Checks

Render automatically monitors your service:

- **Endpoint**: `/api/health`
- **Interval**: Every 60 seconds
- **Timeout**: 10 seconds
- **Failure Threshold**: 3 consecutive failures → restart

**Health Check Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-11T12:00:00Z"
}
```

---

## 🔐 Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host/db?sslmode=require` |
| `GROQ_API_KEY` | Groq API key for LLM | `gsk_...` |
| `ENCRYPTION_KEY` | AES-256 encryption key | Generated (32+ chars) |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHON_VERSION` | Python version | `3.11.0` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TZ` | Timezone | `UTC` |

### Setting Variables in Render

1. Go to your service dashboard
2. Click **"Environment"** tab
3. Click **"Add Environment Variable"**
4. Enter key and value
5. Click **"Save Changes"**
6. Service will restart automatically

**⚠️ Important**: Changes to environment variables trigger automatic redeployment.

---

## 📊 Monitoring & Logs

### Viewing Logs

**Real-time Logs:**
1. Navigate to service dashboard
2. Click **"Logs"** tab
3. View streaming logs in real-time

**Log Levels:**
- `INFO`: General information
- `WARNING`: Non-critical issues
- `ERROR`: Errors requiring attention

### Metrics (Paid Plans)

On Starter plan and above:
- **CPU Usage**: Monitor CPU utilization
- **Memory Usage**: Track memory consumption
- **Request Metrics**: Response times, error rates
- **Custom Metrics**: Application-specific metrics

### Alerts

Configure alerts for:
- Service downtime
- High error rates
- Resource exhaustion
- Health check failures

---

## 🔧 Troubleshooting

### Build Failures

#### Error: `ModuleNotFoundError`

**Cause**: Missing dependency in `requirements.txt`

**Solution**:
```bash
# Check requirements.txt
cat requirements.txt

# Add missing dependency
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push
```

#### Error: `Port already in use`

**Cause**: Start command not using `$PORT`

**Solution**: Update start command:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

#### Error: `Python version mismatch`

**Cause**: Wrong Python version specified

**Solution**: 
- Set `PYTHON_VERSION=3.11.0` in environment variables
- Or update `runtime.txt`

### Runtime Errors

#### Error: `Database connection failed`

**Symptoms**: Health check fails, logs show connection errors

**Solutions**:
1. Verify `DATABASE_URL` is correct
2. Check database allows connections from Render IPs
3. Ensure SSL is enabled (`sslmode=require`)
4. Verify database credentials

#### Error: `ENCRYPTION_KEY not found`

**Symptoms**: API fails to encrypt/decrypt credentials

**Solution**: Add `ENCRYPTION_KEY` to environment variables

#### Error: `GROQ_API_KEY invalid`

**Symptoms**: AI analysis fails

**Solution**: 
1. Verify API key is correct
2. Check API key hasn't expired
3. Verify API key has necessary permissions

### Performance Issues

#### Problem: Cold Starts

**Symptoms**: First request after inactivity is slow (15-30 seconds)

**Causes**: 
- Free tier: Services sleep after 15 minutes inactivity
- First request wakes up the service

**Solutions**:
- Upgrade to Starter plan ($7/month) - eliminates cold starts
- Implement health check pings to keep service warm
- Use Render's scheduled jobs to ping service

#### Problem: Slow Response Times

**Symptoms**: API responses take > 5 seconds

**Solutions**:
1. **Database Optimization**:
   - Check query performance
   - Verify indexes are being used
   - Consider connection pooling

2. **Code Optimization**:
   - Profile application
   - Optimize slow endpoints
   - Cache frequently accessed data

3. **Resource Limits**:
   - Upgrade plan for more resources
   - Check memory/CPU usage

#### Problem: Timeout Errors

**Symptoms**: Requests timeout before completion

**Solutions**:
1. Increase timeout in Render settings
2. Optimize long-running operations
3. Consider background tasks for heavy processing

---

## ⚡ Performance Optimization

### Database Optimization

- ✅ **Indexes**: 15+ performance indexes already created
- ✅ **Connection Pooling**: Configured in `database.py`
- ✅ **Query Optimization**: Use EXPLAIN ANALYZE for slow queries

### Application Optimization

- ✅ **Async Endpoints**: FastAPI async support
- ✅ **Response Caching**: Consider Redis for caching
- ✅ **Background Tasks**: Use FastAPI BackgroundTasks for heavy operations

### Render-Specific Optimizations

- **Health Checks**: Keep service warm
- **Resource Allocation**: Upgrade plan if needed
- **Region Selection**: Choose closest to users/database

---

## 🔒 Security Checklist

Before going to production:

- [ ] ✅ HTTPS enabled (automatic on Render)
- [ ] ✅ All environment variables set
- [ ] ✅ `ENCRYPTION_KEY` is unique and secure
- [ ] ✅ Database uses SSL (`sslmode=require`)
- [ ] ✅ CORS configured correctly
- [ ] ✅ No secrets in code or logs
- [ ] ✅ Rate limiting implemented (recommended)
- [ ] ✅ Input validation on all endpoints
- [ ] ✅ Error messages don't expose sensitive info
- [ ] ✅ Regular security updates

**📖 See [SECURITY.md](./SECURITY.md) for detailed security documentation**

---

## 💰 Pricing & Plans

### Free Tier

- ✅ 750 hours/month free
- ✅ Automatic SSL certificates
- ✅ Health checks
- ⚠️ Cold starts after 15min inactivity
- ⚠️ Limited resources (512MB RAM)

### Starter Plan ($7/month)

- ✅ No cold starts
- ✅ More resources (512MB RAM, 0.5 CPU)
- ✅ Priority support
- ✅ Custom domains

### Professional Plan ($25/month)

- ✅ Even more resources
- ✅ Auto-scaling
- ✅ Advanced monitoring
- ✅ Dedicated support

**💡 Recommendation**: Start with Free tier, upgrade to Starter if cold starts become an issue.

---

## 📚 Additional Resources

### Render Documentation

- [Render Docs](https://render.com/docs)
- [Python on Render](https://render.com/docs/deploy-python)
- [Environment Variables](https://render.com/docs/environment-variables)
- [Health Checks](https://render.com/docs/health-checks)
- [Logs & Monitoring](https://render.com/docs/log-streaming)

### Support

- **Render Support**: support@render.com
- **Render Community**: [community.render.com](https://community.render.com)
- **Status Page**: [status.render.com](https://status.render.com)

---

## 🎯 Next Steps

After successful deployment:

1. ✅ Test all endpoints
2. ✅ Monitor logs for errors
3. ✅ Set up alerts
4. ✅ Configure custom domain (optional)
5. ✅ Set up CI/CD (optional)
6. ✅ Implement monitoring (optional)

---

<div align="center">

**Happy Deploying! 🚀**

[⬆ Back to Top](#-deployment-guide---rendercom)

</div>
