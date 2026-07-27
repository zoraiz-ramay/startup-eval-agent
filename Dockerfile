# ============================================
# Vite (React) + FastAPI Multi-Stage Dockerfile
# Uses pre-built DAA base images for speed
# ============================================

# --- Stage 1: Build frontend ---
FROM 580347574525.dkr.ecr.us-west-2.amazonaws.com/daa-base-node:latest AS frontend

WORKDIR /frontend

# Copy frontend package files for layer caching
COPY ui/package.json ui/package-lock.json* ./

# --include=dev is required because vite/typescript are devDependencies and
# the base image sets NODE_ENV=production which skips them by default.
RUN npm install --include=dev

# Copy frontend source and build
COPY ui/ .
RUN npm run build

# --- Stage 2: Python FastAPI backend ---
FROM 580347574525.dkr.ecr.us-west-2.amazonaws.com/daa-base-python:latest

WORKDIR /app

# Build arguments for private registry access
ARG GITLAB_TOKEN

# Copy requirements first for layer caching
COPY requirements.txt .

# Install app-specific Python dependencies (base packages already in image)
RUN pip install --no-cache-dir -r requirements.txt

# Install Redis
RUN apt-get update && \
    apt-get install -y --no-install-recommends redis-server && \
    rm -rf /var/lib/apt/lists/*

# Copy application code
COPY --chown=appuser:appuser . .

# Copy built frontend from Stage 1
COPY --from=frontend --chown=appuser:appuser /frontend/dist ./static

# Ensure redis data dir exists and is writable
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["sh", "start.sh"]
