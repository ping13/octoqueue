#!/bin/bash
# deploy.sh

# Exit on error
set -e

# Configuration
SERVICE_NAME=$1
PROJECT_ID=$2  # make sure this is $(gcloud config get-value project)
IMAGE_NAME=$3
REGION="europe-west6"

# Push the image to Google Container Registry
echo "Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}

# Deploy to Cloud Run, use the .env file to pass al env vars 
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --set-env-vars="$(uv run dotenv list | paste -s -d ',' -)"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo "Deployment complete!"
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test with:\n curl -X POST -H 'Content-Type: application/json' -H 'X-API-Key: ${API_KEY}' -d '{\"data\": {\"test\": true}}' ${SERVICE_URL}/create-job"
