# BluHands — Service URLs & Ports

All services run on the EC2 instance behind `app.bluehands.ai`.  
Ports listed are the **host (EC2) ports** — access via `http://<EC2-IP>:<port>` or `https://app.bluehands.ai:<port>` if your firewall/security group allows them.

## Public (via nginx reverse proxy)

| Service | URL | Notes |
|---------|-----|-------|
| **App (frontend)** | https://app.bluehands.ai | Main user-facing app |
| **Forge API** | https://app.bluehands.ai/api/v1/ | Control-plane REST API |
| **OpenHands API** | https://app.bluehands.ai/api/ | Conversation + agent API |
| **OpenHands WebSocket** | wss://app.bluehands.ai/ws | Live agent stream |

> nginx listens on host port **8080** (→ container port 80). An upstream proxy / AWS load balancer routes 80/443 → 8080.

---

## Internal / Direct EC2 Ports

> Requires the EC2 Security Group to allow inbound on the relevant port.  
> Not exposed through nginx — access directly via the EC2 IP.

| Service | Host Port | URL | Credentials |
|---------|-----------|-----|-------------|
| **Grafana** | 3001 | http://\<EC2-IP\>:3001 | admin / `$GRAFANA_ADMIN_PASSWORD` (default: `admin`) |
| **Prometheus** | 9090 | http://\<EC2-IP\>:9090 | none |
| **Flower** (Celery monitor) | 5555 | http://\<EC2-IP\>:5555 | none (add auth in prod) |
| **Forge API** (direct) | 8001 | http://\<EC2-IP\>:8001 | Bearer token |
| **bluhands-agent** | 8100 | http://\<EC2-IP\>:8100/health | internal only |
| **OpenHands server** | 3000 | http://\<EC2-IP\>:3000 | internal only |
| **MinIO console** | 9101 | http://\<EC2-IP\>:9101 | `$MINIO_ROOT_USER` / `$MINIO_ROOT_PASSWORD` |
| **MinIO S3 API** | 9100 | http://\<EC2-IP\>:9100 | S3-compatible |
| **PostgreSQL** | 5433 | `psql -h <EC2-IP> -p 5433` | `$POSTGRES_USER` / `$POSTGRES_PASSWORD` |
| **Redis** | 6379 | internal only (no host binding) | — |

---

## Quick Reference — What to Open in Security Group

To access monitoring from your browser, ensure inbound TCP rules exist for:

- **3001** — Grafana
- **9090** — Prometheus  
- **5555** — Flower

Ports **8100**, **3000**, **9100/9101**, **5433** should stay closed to the internet.
