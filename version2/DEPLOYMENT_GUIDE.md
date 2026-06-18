# Google Cloud Run Deployment Guide - Signal Backend

Complete step-by-step guide for deploying your FastAPI backend to Google Cloud Run with CI/CD.

---

## 📋 Prerequisites

### 1. Install Google Cloud CLI

**macOS:**
```bash
brew install google-cloud-sdk
gcloud init
```

**Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

**Windows (PowerShell):**
```powershell
(New-Object Net.WebServiceProxy).GetType().Namespace
# OR download from: https://cloud.google.com/sdk/docs/install-sdk
```

### 2. Verify Installation
```bash
gcloud --version
docker --version
```

---

## 🚀 Quick Start (5 minutes)

### Option A: Automated Deployment Script

```bash
cd version2/backend
chmod +x deploy.sh

# Deploy with defaults (us-central1)
./deploy.sh your-gcp-project-id

# Deploy with custom region and service name
./deploy.sh your-gcp-project-id us-west1 my-backend-service
```

### Option B: Manual Deployment

```bash
# 1. Set your project
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID

# 2. Build Docker image
cd version2/backend
docker build -t gcr.io/$PROJECT_ID/signal-backend:latest .

# 3. Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/signal-backend:latest

# 4. Deploy to Cloud Run
gcloud run deploy signal-backend \
  --image gcr.io/$PROJECT_ID/signal-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars ENVIRONMENT=production

# 5. View logs
gcloud run logs read signal-backend --region us-central1 --limit 50
```

---

## 🔐 Setting Up Environment Variables & Secrets

### 1. Create `.env.production` file

```bash
cat > version2/backend/.env.production << 'EOF'
# Environment
ENVIRONMENT=production
DEBUG=false

# Database
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/signal
MONGODB_DB_NAME=signal_prod

# Redis
REDIS_URL=redis://redis-host:6379/0

# API Keys
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
GOOGLE_API_KEY=your-key-here

# Security
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Server
WORKERS=4
WORKER_TIMEOUT=600
EOF
```

### 2. Set Secrets in Google Cloud Secret Manager

```bash
# Create secrets
echo -n "$(cat .env.production | grep MONGODB_URI=)" | \
  gcloud secrets create mongodb-uri --data-file=-

# Set env var to reference the secret
gcloud run deploy signal-backend \
  --set-secrets MONGODB_URI=mongodb-uri:latest \
  --region us-central1
```

### 3. Using Cloud Run UI

Go to [Cloud Console](https://console.cloud.google.com/run) → click your service → Edit & Deploy:

1. Scroll to "Runtime environment variables"
2. Click "Reference a secret"
3. Select your secret from Secret Manager
4. Deploy

---

## 🔄 Environment Variables Checklist

```bash
# Essential for production
☐ ENVIRONMENT=production
☐ DEBUG=false
☐ MONGODB_URI=your-connection-string
☐ MONGODB_DB_NAME=signal_prod
☐ REDIS_URL=your-redis-url

# API Keys (use Secret Manager)
☐ OPENAI_API_KEY
☐ ANTHROPIC_API_KEY
☐ GOOGLE_API_KEY

# Security
☐ SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
☐ JWT_ALGORITHM=HS256

# Performance
☐ WORKERS=4 (for 2 CPU)
☐ WORKER_TIMEOUT=600
☐ ENABLE_METRICS=true

# Optional
☐ LOG_LEVEL=info
☐ CORS_ORIGINS=your-frontend-domain
```

---

## 🔗 Connecting External Services

### MongoDB Atlas (Recommended)

1. Create a cluster at [mongodb.com](https://cloud.mongodb.com)
2. Create a database user with IP whitelist: `0.0.0.0/0` (Cloud Run dynamic IPs)
3. Get connection string: `mongodb+srv://user:pass@cluster.mongodb.net/db?retryWrites=true`
4. Set as `MONGODB_URI` secret in Cloud Run

### Redis

**Option 1: Google Memorystore**
```bash
# Create Memorystore instance
gcloud memorystore instances create signal-redis \
  --size=2 \
  --region=us-central1 \
  --redis-version=7.0

# Get host/port and set REDIS_URL
gcloud memorystore instances describe signal-redis --region=us-central1
```

**Option 2: External Redis**
- Set `REDIS_URL` to your Redis connection string

### Celery Workers

For background task processing, deploy separate Celery worker services:

```bash
# Create a Cloud Run job for Celery workers
gcloud run jobs create signal-celery-worker \
  --image gcr.io/$PROJECT_ID/signal-backend:latest \
  --command "celery" \
  --args "-A,workers.celery_app,worker,--loglevel=info" \
  --region us-central1 \
  --set-env-vars ENVIRONMENT=production
```

---

## 🚦 Configuring Cloud Run Instance

### Memory & CPU Options (Balance performance & cost)

```bash
# Lightweight (small datasets)
--memory 512Mi --cpu 1

# Standard (recommended)
--memory 2Gi --cpu 2

# High performance
--memory 4Gi --cpu 4
--memory 8Gi --cpu 4

# Max resources
--memory 8Gi --cpu 4
```

### Auto-scaling

```bash
# Set concurrency (requests per instance)
--concurrency=100

# Min/max instances
--min-instances=1     # Always-on minimum
--max-instances=100   # Auto-scale max

# For API with bursty traffic:
--min-instances=2
--max-instances=50

# For always-on service:
--min-instances=5
--max-instances=100
```

### Timeout Configuration

```bash
# Default: 300s (5 min)
# Max: 3600s (1 hour)
--timeout=3600  # For long-running queries

# Typical for APIs:
--timeout=600   # 10 minutes
```

---

## 📊 Monitoring & Logs

### View Real-time Logs
```bash
gcloud run logs read signal-backend --region us-central1 --limit 50 --follow
```

### View Metrics
```bash
# CPU utilization
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision"' \
  --limit 10

# Or go to Cloud Console:
# https://console.cloud.google.com/monitoring/dashboards/custom
```

### Set up Error Alerting
```bash
# Create log-based metric for errors
gcloud logging metrics create error_count \
  --log-filter='severity="ERROR" resource.type="cloud_run_revision"'

# Create alert policy in Cloud Console
```

---

## 🔄 GitHub Actions CI/CD Setup

### 1. Create Service Account for GitHub

```bash
# Create service account
gcloud iam service-accounts create github-workflows \
  --display-name="GitHub Workflows"

# Grant Cloud Run admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:github-workflows@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.admin

# Grant Cloud Build permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:github-workflows@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/cloudbuild.builds.editor
```

### 2. Set up Workload Identity Federation

```bash
# Create workload identity pool
gcloud iam workload-identity-pools create github \
  --project=$PROJECT_ID \
  --location=global \
  --display-name=GitHub

# Create workload identity provider
gcloud iam workload-identity-pools providers create-oidc github \
  --project=$PROJECT_ID \
  --location=global \
  --workload-identity-pool=github \
  --display-name=GitHub \
  --attribute-mapping=google.subject=assertion.sub,attribute.actor=assertion.actor \
  --issuer-uri=https://token.actions.githubusercontent.com

# Generate service account key
gcloud iam workload-identity-pools keys list \
  --workload-identity-pool=github \
  --location=global --project=$PROJECT_ID
```

### 3. Add GitHub Secrets

Go to GitHub Settings → Secrets and add:

```bash
GCP_PROJECT_ID = your-project-id
WIF_PROVIDER = projects/{project-number}/locations/global/workloadIdentityPools/github/providers/github
WIF_SERVICE_ACCOUNT = github-workflows@{project-id}.iam.gserviceaccount.com
```

### 4. How CI/CD Works

Every push to `main` or `production`:
1. ✅ Checks out code
2. 🔐 Authenticates to GCP using Workload Identity
3. 🐳 Builds Docker image
4. 📤 Pushes to Google Container Registry
5. 🚀 Deploys to Cloud Run
6. 🏥 Runs health check

---

## 🧪 Testing Your Deployment

### 1. Health Check
```bash
SERVICE_URL=$(gcloud run services describe signal-backend \
  --region us-central1 --format='value(status.url)')

curl $SERVICE_URL/health
# Expected: {"status": "ok"}
```

### 2. Test API Endpoints
```bash
# Get datasets
curl -H "Authorization: Bearer $TOKEN" $SERVICE_URL/api/datasets

# Create test dataset
curl -X POST $SERVICE_URL/api/datasets/upload \
  -F "file=@test_data.csv"
```

### 3. Load Testing
```bash
# Install k6
brew install k6

# Run load test
k6 run --vus 10 --duration 30s - << 'EOF'
import http from 'k6/http';
import { check } from 'k6';

export default function () {
  let res = http.get('https://your-service.run.app/health');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 1s': (r) => r.timings.duration < 1000,
  });
}
EOF
```

---

## 💰 Cost Optimization

### Recommended Production Setup

```bash
# Standard production configuration
gcloud run deploy signal-backend \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 2 \
  --max-instances 50 \
  --concurrency 100
```

**Estimated Monthly Cost (us-central1):**
- Min instances: 2 × $24 = $48
- Computing: ~$40 (with 50M request/month average)
- Storage & logs: ~$10
- **Total: ~$100-150/month**

### Cost-Saving Tips

```bash
# Use fewer min instances during off-peak
gcloud run deploy signal-backend \
  --min-instances 1  # Instead of 2

# Set appropriate timeout
--timeout 600  # Instead of 3600

# Use smaller memory for non-heavy operations
--memory 1Gi  # Instead of 2Gi
```

---

## 🚨 Troubleshooting

### Container fails to start

```bash
# Check logs
gcloud run logs read signal-backend --limit 100

# Common issues:
# - Port not listening on 8080
# - Missing dependencies in requirements.txt
# - Syntax errors in main.py
```

### High latency or timeouts

```bash
# Check revision metrics
gcloud run revisions list signal-backend --region us-central1

# Increase timeout
--timeout 1800

# Check if it's cold-start issue
--min-instances 2  # Keep warm
```

### Database connection failures

```bash
# Verify connection string is valid
echo $MONGODB_URI

# Check IP allowlist in MongoDB Atlas
# Cloud Run uses dynamic IPs, allow 0.0.0.0/0

# Use VPC connector for private databases
--vpc-connector=my-vpc-connector
```

---

## 🔐 Security Best Practices

```bash
# 1. Don't make public if not needed
gcloud run deploy signal-backend \
  --no-allow-unauthenticated

# 2. Use Cloud Armor for DDoS protection
# Set up in Cloud Console → Artifacts → Cloud Armor

# 3. Always use secrets for sensitive data
# Never commit .env files!

# 4. Enable VPC connector for private database access
--vpc-connector=my-vpc-connector

# 5. Set up Cloud IAM for service account access
gcloud run services add-iam-policy-binding signal-backend \
  --member=serviceAccount:my-service-account@project.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

---

## 📚 Useful Links

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Container Registry](https://console.cloud.google.com/gcr)
- [Cloud Run Services Dashboard](https://console.cloud.google.com/run)
- [Secret Manager](https://console.cloud.google.com/security/secret-manager)
- [Monitoring & Logging](https://console.cloud.google.com/monitoring)
- [Pricing Calculator](https://cloud.google.com/products/calculator)

---

## ✅ Deployment Checklist

- [ ] Docker image builds locally: `docker build -t test .`
- [ ] Environment variables file created
- [ ] MongoDB connection string works
- [ ] Redis connection works (if using)
- [ ] Celery workers configured (if needed)
- [ ] GitHub Actions secrets added
- [ ] Service account created for CI/CD
- [ ] Cloud Run service deployed
- [ ] Health check responding
- [ ] API endpoints tested
- [ ] Logs configured and monitored
- [ ] Auto-scaling settings configured
- [ ] Secrets stored in Secret Manager
- [ ] Error alerting configured

---

## 🆘 Need Help?

```bash
# Detailed logs with all metadata
gcloud run logs read signal-backend \
  --region us-central1 \
  --format=json \
  --limit 100

# Check service configuration
gcloud run services describe signal-backend --region us-central1

# Test locally with same environment
docker run -e ENVIRONMENT=production \
  -p 8080:8080 \
  --env-file .env.production \
  gcr.io/$PROJECT_ID/signal-backend:latest
```

---

**Happy Deploying! 🚀**
