#!/usr/bin/env bash
set -euo pipefail

echo "Stopping existing containers (if any)..."
docker compose down

echo "Building sandbox image..."
docker build -f Dockerfile.sandbox -t codezen-sandbox:latest .

echo "Starting API, worker, and Redis in the background (redeploy)..."
docker compose up -d --build

echo "Redeployment successful!"
