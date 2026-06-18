#!/bin/bash
# Manual deployment script for Google Cloud Run
# Usage: ./deploy.sh [project-id] [region] [service-name]

set -e

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
SERVICE_NAME=${3:-signal-backend}
BACKEND_PATH="version2/backend"

if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP Project ID not provided"
    echo "Usage: $0 [project-id] [region] [service-name]"
    exit 1
fi

echo "🚀 Starting deployment to Google Cloud Run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Project ID: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo "🎯 Service: $SERVICE_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Authenticate
echo "✓ Step 1/6: Authenticating with Google Cloud..."
gcloud auth list --filter=status:ACTIVE --format="value(account)"

# Step 2: Set project
echo "✓ Step 2/6: Setting GCP project..."
gcloud config set project $PROJECT_ID

# Step 3: Build Docker image
echo "✓ Step 3/6: Building Docker image..."
docker build \
    -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    -t gcr.io/$PROJECT_ID/$SERVICE_NAME:$(date +%Y%m%d-%H%M%S) \
    -f $BACKEND_PATH/Dockerfile \
    $BACKEND_PATH

# Step 4: Push to Container Registry
echo "✓ Step 4/6: Pushing image to Google Container Registry..."
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Step 5: Deploy to Cloud Run
echo "✓ Step 5/6: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 100 \
    --min-instances 1 \
    --port 8080 \
    --set-env-vars ENVIRONMENT=production

# Step 6: Get service URL
echo "✓ Step 6/6: Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --format 'value(status.url)')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Service URL: $SERVICE_URL"
echo "📊 Logs: gcloud run logs read $SERVICE_NAME --region $REGION --limit 50"
echo "⚙️  Manage: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
echo ""
echo "💡 Test the service:"
echo "   curl $SERVICE_URL/health"
echo ""
