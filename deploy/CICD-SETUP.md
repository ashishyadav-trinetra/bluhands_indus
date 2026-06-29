# CI/CD — push to deploy

Push to `main` → GitHub Actions SSHes into the EC2 box → `scripts/deploy.sh`
pulls and rebuilds **only what changed**. One-time setup below.

## How it works
- `.github/workflows/deploy.yml` runs on every push to `main` (and a manual
  "Run workflow" button). It opens an SSH session to the server and runs
  `scripts/deploy.sh`.
- `scripts/deploy.sh` does `git pull --rebase --autostash` (protects the
  server's local `.env` secrets), then looks at the changed paths and acts:
  | Changed path | Action |
  |---|---|
  | `deploy/nginx-host.conf` | `sudo cp` → `nginx -t && nginx -s reload` |
  | `openhands-server/**` | `docker compose build openhands && up -d openhands` |
  | `docker-compose.yml` | `docker compose up -d` (apply env/ports) |
  | `frontend/**` | `docker compose build --no-cache frontend && up -d frontend` |
  | `control-plane/**` | `docker compose up -d api worker` (bind-mounted) |
  | `agent/**` | `docker compose build agent && up -d agent` |

## One-time setup

### 1. GitHub repo secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:
- `EC2_HOST` — the server IP/hostname (e.g. `54.87.249.176`).
- `EC2_USER` — the SSH user (e.g. `deployuser`).
- `EC2_SSH_KEY` — a **private** SSH key whose public half is in that user's
  `~/.ssh/authorized_keys` on the server. (Generate a dedicated deploy key:
  `ssh-keygen -t ed25519 -f deploy_key -N ""`, add `deploy_key.pub` to the
  server, paste `deploy_key` here.)
- `EC2_PORT` — optional, defaults to 22.

### 2. Passwordless sudo for the nginx step (only if you deploy nginx changes)
`scripts/deploy.sh` runs `sudo cp` + `sudo nginx` when `deploy/nginx-host.conf`
changes. Give the deploy user passwordless sudo for just those two commands:
```bash
echo "$USER ALL=(root) NOPASSWD: /bin/cp deploy/nginx-host.conf /etc/nginx/sites-available/bluhands, /usr/sbin/nginx" | sudo tee /etc/sudoers.d/bluhands-deploy
```
(Adjust paths to match `which nginx`. If you'd rather keep nginx manual, just
apply nginx changes by hand — every other path deploys automatically.)

### 3. Cloudflare cache (frontend deploys)
A frontend rebuild bakes a new bundle. Purge Cloudflare after a frontend deploy
so the new JS is served. To automate later, add a `curl` purge call to the end
of the frontend branch in `deploy.sh` using a Cloudflare API token + zone id.

## Recommended hardening
The server's **real secrets currently live in tracked `.env*` files**, which is
why the deploy uses `--autostash`. Cleaner long-term: keep the tracked files as
**templates only** and put real values in a **gitignored** `.env` (Docker
`env_file`) or a secrets manager. Then pulls never touch secrets and the
autostash dance goes away.

## Test it
```bash
# manual run on the server (no CI needed):
cd ~/var/www/bluhands_indus && bash scripts/deploy.sh

# or push a trivial change and watch GitHub → Actions → "Deploy to EC2".
```
