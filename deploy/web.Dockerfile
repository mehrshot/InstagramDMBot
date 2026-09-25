# The public entry point: builds the shop panel and serves it, together with the API, through
# Caddy (automatic HTTPS). Build context is the repository root (see docker-compose.yml).

FROM node:22-alpine AS panel
WORKDIR /panel
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The panel calls the API at this address; it is baked into the build.
ARG VITE_API_URL
ARG VITE_SUPPORT_EMAIL
RUN test -n "$VITE_API_URL" || (echo "VITE_API_URL is required" && exit 1)
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=panel /panel/dist /srv/panel
