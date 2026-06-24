# Medusa golden image (T-A02). Runs the create-medusa-app project mounted at /app.
# Pin the Node version Medusa v2 supports. Adjust the start command to match the
# scripts in the generated app's package.json (create-medusa-app sets these).
FROM node:20-bookworm-slim

WORKDIR /app

# The app source is bind-mounted by docker-compose (./app -> /app). On first run,
# install deps inside the container if node_modules isn't present, then migrate
# and start. (For a true immutable golden image, COPY the app in + npm ci here.)
ENV NODE_ENV=development

EXPOSE 9000

# v2: `medusa db:migrate` applies migrations; `npm run dev` runs `medusa develop`.
# If node_modules is missing (fresh bind mount), install first.
CMD ["sh", "-c", "[ -d node_modules ] || npm install; npx medusa db:migrate || true; npm run dev"]
