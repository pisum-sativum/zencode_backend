$ErrorActionPreference = "Stop"

Write-Host "Building sandbox image..."
docker build -f Dockerfile.sandbox -t codezen-sandbox:latest .

Write-Host "Starting API, worker, and Redis..."
docker compose up --build
