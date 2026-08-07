# Multi-stage build for the Vite (React) SPA served by nginx.
# Reconstructed to match the running startup_eval_agent-ui container
# (nginx 1.27.5, listens on 8080, proxies /api + /health to api:8000).

# --- Stage 1: build the static assets ---
FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies (no lockfile is committed, so use npm install)
COPY package.json package-lock.json* ./
RUN npm install

# Build the SPA
COPY . .
RUN npm run build

# --- Stage 2: serve with nginx ---
FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
