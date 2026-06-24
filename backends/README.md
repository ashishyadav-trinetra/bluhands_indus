# catalog — PLANNED (T-A02) · pre-built industry backends (black boxes)

Each entry is a *golden image + config/plugins on upstream* (never a fork) behind
a stable, versioned **capability manifest** the agent reads. The control plane
provisions a per-tenant instance; the BluHands agent only *consumes* the API.

Layout: `catalog/<industry>/<backend>/` →
`Dockerfile`/helm · `seed/` · `openapi.json` · `capability-manifest.json` · `adapter/`.
