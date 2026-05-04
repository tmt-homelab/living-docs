

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (DNS TTL limits immediate failover capability) |
| **Blast radius if down** | All external ingress traffic (AI, Home Assistant, Plex, etc.) unreachable from public internet. Internal services on `ai-services` network may still communicate directly. |
| **Recovery time today** | Auto-restart (`unless-stopped`), but full TLS restoration depends on `certbot` container health. |
| **Owner** | Homelab Admin (registered by `claude-code` in CMDB) |

## What this service actually does

Caddy acts as the fleet edge ingress, terminating TLS and routing traffic to backend services. It provisions wildcard certificates (`*.themillertribe-int.org`) via a companion `certbot` container using Cloudflare DNS-01 challenges.

Other fleet services use it via standard HTTP/HTTPS ports (80/443). Backend containers on the `ai-services` and `proxy` networks do not expose ports to the host; they rely entirely on Caddy's `Caddyfile` for routing.

This is NOT a load balancer for active-active replicas across multiple hosts. It is NOT a Zero Trust tunnel (Cloudflared removed 2026-04-10). It is NOT a general purpose web server for static content outside the fleet.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp01-proxy/docker-compose.yml` |
| **Image** | `caddy:2-alpine` |
| **Pinning policy** | Tag-floating (risk: minor updates without digest pinning) |
| **Resource caps** | ? (not defined in compose) |
| **Volumes** | `/mnt/docker/stacks/dockp01-proxy/Caddyfile` (RO), `caddy-data` (state), `caddy-config` (state), `letsencrypt-data` (shared with certbot) |
| **Networks** | `ai-services` (external), `proxy` (external) |
| **Secrets** | `CF_USER`, `CF_APIKEY` (injected via `.env` / 1Password Connect) |
| **Healthcheck** | `wget -q -O /dev/null http://127.0.0.1:80/health` (3 retries, 30s interval) |

### Configuration shape

Configuration is driven by the bind-mounted `Caddyfile` at `/etc/caddy/Caddyfile`. Environment variables (`CF_USER`, `CF_APIKEY`) are consumed only by the companion `certbot` service, not Caddy directly. Logging driver set to `json-file` (Splunk driver disabled due to incident 2026-04-10).

## Dependencies

### Hard (service cannot start or operate without these)
- **`certbot`** — Caddy depends on `service_healthy` condition. Without certs, TLS handshakes fail.
- **Cloudflare API** — Required for DNS-01 challenge validation during renewal.
- **DNS Records