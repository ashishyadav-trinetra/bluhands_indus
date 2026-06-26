# BluHands frontend — production image (React Router 7 + Vite, served static).
# Multi-stage: build with Node, then serve the static build with sirv on :3000.

# ---- build ------------------------------------------------------------------
FROM node:22-slim AS build
WORKDIR /app

# Install deps with the lockfile for reproducibility, then build.
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
# Vite reads VITE_* at BUILD time. They must be build ARGs AND exported to ENV so
# `npm run build` (Vite) actually bakes them into the bundle. On a remote deploy,
# VITE_API_BASE_URL MUST be the public URL the browser can reach (NOT localhost).
ARG VITE_API_BASE_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

# ---- runtime ----------------------------------------------------------------
FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production
RUN npm i -g sirv-cli@3 && groupadd --system app && useradd --system --gid app web
COPY --from=build --chown=web:app /app/build ./build
USER web
EXPOSE 3000
# --single for SPA-style fallback routing; bind all interfaces for Docker.
CMD ["sirv", "build", "--single", "--host", "0.0.0.0", "--port", "3000"]
