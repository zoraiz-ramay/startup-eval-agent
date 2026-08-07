#!/bin/sh
set -e

# Start Redis
echo "Starting Redis..."
redis-server /app/redis.conf --daemonize yes

# Wait for Redis to be ready
until redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 0.5
donestart
echo "Redis is ready."

# Start the application
exec gunicorn api.main:app \
  --bind 0.0.0.0:8080 \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout 300 \
  --graceful-timeout 30
