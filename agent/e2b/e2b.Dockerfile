# BluHands E2B sandbox template — Node-capable build environment.
#
# Each client build runs in a fresh, isolated E2B microVM created from THIS image.
# Baking Node + npm + git in here (instead of installing per build) removes the
# biggest cold-start cost. Build & push with the E2B CLI (see README.md):
#
#   e2b template build --name bluhands-node
#
# E2B layers its `envd` init on top of this image during the build.

FROM e2bdev/base:latest

# Node 22 (LTS) + git + build tools for native npm deps.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git ca-certificates build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g npm@latest \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# The runner uploads the starter here and runs npm install/build/start in it.
RUN mkdir -p /home/user/app
WORKDIR /home/user/app

# OPTIONAL (bigger speed win): bake the golden starter's node_modules so each
# build skips `npm install` entirely. Uncomment and copy your starter's lockfile:
#   COPY package.json package-lock.json ./
#   RUN npm ci
# Trade-off: the template must be rebuilt whenever the starter's deps change.
