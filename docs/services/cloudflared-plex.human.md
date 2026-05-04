

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Minutes (Remote admin access lost, streaming unaffected) |
| **Blast radius if down** | External Web UI unreachable. Core Plex streaming via WAN port-forward remains active. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Manual token refresh if revoked. |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Establishes an outbound Cloudflare Tunnel connection to expose the Plex Web UI to the public internet. It terminates TLS at the Cloudflare edge and forwards traffic to Caddy (internal), which reverse-proxies to Plex.

- **Primary purpose:** Secure remote administration of Plex without opening inbound ports on the firewall.
- **Consumer pattern:** Inbound HTTP from Cloudflare Edge -> Outbound HTTP to `media` network.
- **What it is NOT:** This service does NOT handle media streaming traffic. Video transcoding and streaming bypass this tunnel, utilizing the WAN port-forward + Caddy `external_tls` vhost instead. Confusing tunnel logs with streaming latency is a common debugging error.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/cloudflared-plex/docker-compose.yml` |
| **Image** | `cloudflare/cloudflared:latest` |
| **Pinning policy** | Tag-floating (`latest`). **Risk:** Unpredictable updates. |
| **Resource caps** | `?` (None defined in compose) |
| **Volumes** | `./config.yml` (RO), `./credentials.json` (RO). No writable container volumes. |
| **Networks** | `media` (external), `infra-services` (external) |
| **Secrets** | `CF_TUNNEL_TOKEN_PLEX` (Injected via env var) |
| **Healthcheck** | `wget -q --spider http://localhost:2000/ready` (30s interval) |

### Configuration shape

Configuration is split between environment variables and mounted files.
- **Env:** `TUNNEL_TOKEN` authenticates the tunnel to Cloudflare.
- **YAML:** `/etc/cloudflared/config/config.yml` defines tunnel routes and ingress rules.
- **Credentials:** `credentials.json` stores ephemeral auth for the tunnel daemon.

## Dependencies

### Hard (service cannot start or operate without these)
- **plex** — CMDB lists this as dependency. Tunnel requires network reachability to the target (Caddy/Plex) to establish healthy ingress. If Plex is down, tunnel stays up but returns 502/504 to clients.
- **Cloudflare Control Plane** — Requires outbound 443 connectivity to `trycloudflare.com` / Cloudflare edge.

### Soft (degrade if these are down, but service still