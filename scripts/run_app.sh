#!/usr/bin/env bash
# Run the Startup Evaluation Hydra app locally (Docker compose)
set -euo pipefail

# Build images (if needed)
docker compose build

# Bring up the services in detached mode
docker compose up -d

# Wait for the backend to be healthy (simple poll)
echo "Waiting for backend to become ready..."
for i in {1..30}; do
  if curl -s http://localhost:8000/healthz | grep -q "OK"; then
    echo "Backend ready"
    exit 0
  fi
  sleep 2
done

echo "Backend did not become ready in time" >&2
exit 1