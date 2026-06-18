# 🚀 Google Cloud Run Deployment - Setup Summary

## What's Been Created For You

### 1. **Dockerfile** (`version2/backend/Dockerfile`)
- Multi-stage Docker build (optimized for Cloud Run)
- Non-root user security
- Health check endpoint
- Minimal image size

### 2. **.dockerignore** (`version2/backend/.dockerignore`)
- Excludes unnecessary files from image
- Reduces build size and deployment time

### 3. **Deployment Script** (`version2/backend/deploy.sh`)
- Automated one-command deployment
- No manual steps needed
- Usage: `./deploy.sh your-project-id us-central1 signal-backend`

### 4. **GitHub Actions CI/CD** (`.github/workflows/deploy.yml`)
- Auto-deploy on push to `main` or `production`
- Automatic health checks post-deployment
- Workload Identity Federation (secure, no keys stored)

### 5. **Cloud Build Config** (`cloudbuild.yaml`)
- Alternative CI/CD using Google Cloud Build
- Used when pushing from Cloud Console

### 6. **Comprehensive Deployment Guide** (`DEPLOYMENT_GUIDE.md`)
- Step-by-step setup instructions
- Environment variables checklist
- Troubleshooting guide
- Security best practices
- Cost optimization tips

---

## ⚡ Quick Start (Choose One)

### **Fastest Way - 3 Commands**
```bash
cd version2/backend
chmod +x deploy.sh
./deploy.sh my-gcp-project-id
```

### **Manual Way - Full Control**
```bash
export PROJECT_ID="my-gcp-project-id"
gcloud config set project $PROJECT_ID
cd version2/backend
docker build -t gcr.io/$PROJECT_ID/signal-backend:latest .
docker push gcr.io/$PROJECT_ID/signal-backend:latest
gcloud run deploy signal-backend \
  --image gcr.io/$PROJECT_ID/signal-backend:latest \
  --region us-central1 \
  --memory 2Gi --cpu 2 \
  --set-env-vars ENVIRONMENT=production
```

### **CI/CD Way - Automatic**
```bash
# Just push to GitHub
git add .
git commit -m "Deploy to Cloud Run"
git push origin main
# GitHub Actions automatically deploys!
```

---

## 🔐 Next Steps - Setup Secrets & Environment

### 1. **Install Google Cloud CLI** (if not done)
```bash
# macOS
brew install google-cloud-sdk
gcloud init

# Linux
curl https://sdk.cloud.google.com | bash
```

### 2. **Create Environment for Production**

Copy `.env.example` and configure:
```bash
cp version2/backend/.env.example /tmp/.env.production
# Edit with your actual values:
# - MONGODB_URI (from MongoDB Atlas)
# - REDIS_URL (from Memorystore or external Redis)
# - API KEYS (OpenAI, Anthropic, etc.)
# - SECRET_KEY (generate new one)
```

### 3. **Store Secrets in Google Cloud Secret Manager**
```bash
# Create MongoDB secret
echo "mongodb+srv://user:pass@cluster.mongodb.net/db" | \
  gcloud secrets create mongodb-uri --data-file=-

# Create Redis secret
echo "redis://redis-host:6379/0" | \
  gcloud secrets create redis-url --data-file=-

# Reference in Cloud Run deployment
gcloud run deploy signal-backend \
  --set-secrets MONGODB_URI=mongodb-uri:latest \
  --set-secrets REDIS_URL=redis-url:latest
```

### 4. **Enable GitHub Actions CI/CD** (Recommended)

Go to `.github/workflows/deploy.yml` and add GitHub Secrets:
```bash
GCP_PROJECT_ID="your-project-id"
WIF_PROVIDER="projects/{project-number}/locations/global/workloadIdentityPools/github/providers/github"
WIF_SERVICE_ACCOUNT="github-workflows@project-id.iam.gserviceaccount.com"
```

Then every push to `main` auto-deploys! 🎯

---

## 📊 Resource Configuration

### **Recommended for Production**
```bash
--memory 2Gi          # 2GB RAM
--cpu 2               # 2 vCPU
--min-instances 1     # Always on to avoid cold-start
--max-instances 100   # Auto-scale up to 100
--concurrency 100     # Allow 100 req per instance
--timeout 600         # 10 min timeout per request
```

**Est. Monthly Cost: $100-150**

### **Budget Option (lighter workloads)**
```bash
--memory 1Gi
--cpu 1
--min-instances 1
--max-instances 20
```

**Est. Monthly Cost: $50-80**

### **High Performance (large datasets)**
```bash
--memory 4Gi
--cpu 4
--min-instances 2
--max-instances 50
```

**Est. Monthly Cost: $200-300**

---

## ✅ Deployment Checklist

- [ ] **Install gcloud CLI** - `gcloud init`
- [ ] **Create GCP Project** - go to [console.cloud.google.com](https://console.cloud.google.com)
- [ ] **Enable APIs:**
  ```bash
  gcloud services enable run.googleapis.com
  gcloud services enable containerregistry.googleapis.com
  gcloud services enable secretmanager.googleapis.com
  ```
- [ ] **Create environment variables** - copy from `.env.example`
- [ ] **Create MongoDB Atlas cluster** - [mongodb.com](https://cloud.mongodb.com)
- [ ] **Create Redis** - use Memorystore or external provider
- [ ] **Run deployment script** - `./deploy.sh your-project-id`
- [ ] **Test service** - `curl <service-url>/health`
- [ ] **Set up GitHub Actions** (optional but recommended)
- [ ] **Configure monitoring & alerts**

---

## 🔍 After Deployment - Testing

```bash
# 1. Get your service URL
SERVICE_URL=$(gcloud run services describe signal-backend \
  --region us-central1 --format='value(status.url)')

# 2. Test health endpoint
curl $SERVICE_URL/health

# 3. Check logs
gcloud run logs read signal-backend --region us-central1 -limit 50

# 4. View metrics
gcloud run revisions list signal-backend --region us-central1

# 5. Full service info
gcloud run services describe signal-backend --region us-central1
```

---

## 📚 Full Documentation

**See `DEPLOYMENT_GUIDE.md` for:**
- Detailed step-by-step setup
- Environment variables reference
- Connecting MongoDB, Redis, Celery
- GitHub Actions CI/CD configuration
- Troubleshooting common issues
- Security best practices
- Cost optimization tips
- Load testing
- Monitoring & alerts

---

## 🆘 Common Issues & Quick Fixes

| Issue | Fix |
|-------|-----|
| **Container won't start** | Check logs: `gcloud run logs read {service} --limit 100` |
| **Port not listening** | Ensure app listens on port `8080` (required by Cloud Run) |
| **Missing dependencies** | Update `requirements.txt` and rebuild |
| **Timeout errors** | Increase `--timeout` value (max 3600s) |
| **Cold-start latency** | Set `--min-instances 2` to keep instances warm |
| **Database connection fails** | Verify IP allowlist in MongoDB/Redis, use VPC connector |
| **High costs** | Reduce `--max-instances`, use smaller memory, set `--min-instances 1` |

---

## 📞 CLI Commands Reference

```bash
# Deploy
./deploy.sh my-project-id

# Check status
gcloud run services describe signal-backend --region us-central1

# View logs (live)
gcloud run logs read signal-backend --region us-central1 --follow

# Scale up/down
gcloud run services update signal-backend \
  --min-instances 3 --max-instances 50 --region us-central1

# Get URL
gcloud run services describe signal-backend \
  --region us-central1 --format='value(status.url)'

# Delete service
gcloud run services delete signal-backend --region us-central1

# Set environment variable
gcloud run services update signal-backend \
  --set-env-vars KEY=value --region us-central1
```

---

## 🎯 Next Phase - Production Ready

After initial deployment:

1. ✅ **Set up monitoring**
   - Error tracking (Sentry)
   - Performance monitoring (Datadog)
   - Log analysis (Stack Driver)

2. ✅ **Configure auto-scaling**
   - Load test with k6
   - Tune `--concurrency` and `--max-instances`

3. ✅ **Set up CI/CD pipeline**
   - GitHub Actions auto-deploy
   - Staging environment
   - Automated tests

4. ✅ **Production hardening**
   - Set `--no-allow-unauthenticated` if needed
   - Enable VPC connector
   - Set up Cloud Armor (DDoS protection)

---

**🚀 You're ready to deploy! Start with the Quick Start section above.**

Need help? See `DEPLOYMENT_GUIDE.md` for comprehensive instructions.
