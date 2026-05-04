

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 4 hours (Blog traffic is low volume) |
| **Blast radius if down** | Public ingress to `overlabbed.com` fails immediately. Internal Ghost admin panel remains accessible via local network if `infra-services` bridge is local-only. Mailgun outbound emails may retry but fail if Ghost healthcheck blocks tunnel start. |
| **Recovery time today** | Auto-restart (on-failure). Manual intervention required if `CF_TUNNEL_TOKEN_BLOG` expires or `tmtdockp04` host is lost. |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill` in CMDB) |

## What this service actually does

`cloudflared-blog` establishes an outbound-only TCP tunnel from `tmtdockp04` to Cloudflare's edge network. It exposes the internal `ghost` container (port 2368) to the public internet via `overlabbed.com` without opening inbound firewall ports.

The service does not store blog content, handle database transactions, or process images. It acts purely as a transport layer. It relies on the `ghost` container passing its own healthcheck before the tunnel is allowed to start, ensuring we do not advertise a broken backend to Cloudflare.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/blog/docker-compose.yml` |
| **Image** | `cloudflare/cloudflared:latest` |
| **Pinning policy** | Tag-floating (`latest`). **High Risk**: No SHA256 digest pinned. Updates pull new binaries silently. |
| **Resource caps** | Unknown (Not defined in compose). Typical baseline ~50MB RAM, <5% CPU. |
| **Volumes** | `./cloudflared/config.yml` (bind mount, read-only, contains tunnel config) |
| **Networks** | `blog-internal` (internal overlay to reach Ghost), `infra-services` (external access to Cloudflare edge) |
| **Secrets** | `CF_TUNNEL_TOKEN_BLOG` (Env var, sourced from external secret manager/1Password) |
| **Healthcheck** | `cloudflared tunnel --metrics 127.0.0.1:20241 ready` (Interval: 30s, Timeout: 10s) |

### Configuration shape

Configuration is split between a mounted YAML file and environment variables.
- **`./cloudflared/config.yml`**: Defines tunnel routing rules (host mapping to `127.0.0.1:2368`).
- **Env Var**: `TUNNEL_TOKEN` authenticates the tunnel to Cloudflare.
- **Command**: Fixed to `--config /etc/cloudflared/config.yml tunnel run`. No dynamic config updates supported without restart.

## Dependencies

### Hard (service cannot start or operate without these)
- **`ghost`** — Container must be `service_healthy` before `cloudflared` starts. If Ghost is down, tunnel starts but routes to nothing (or fails healthcheck depending on `config.yml` logic).
- **`infra-services` network** — Requires external routing to reach Cloudflare edge (port 443 outbound).
- **`CF_TUNNEL_TOKEN_BLOG`** — Invalid token causes immediate container exit.

### Soft (degrade if these are down, but service still functional)
- **None** — This is a binary pass-through. If the backend is reachable, tunnel is "up".

### Reverse (services that depend on THIS service)
- **Public Internet** — Users accessing `overlabbed.com`.
- **Ghost** — Does not depend on Cloudflare to run, but relies on it for public ingress.

## State & persistence

- **Tunnel Process**: Stateless. Restarting kills and recreates the connection.
- **Config File**: `./cloudflared/config.yml` on host `tmtdockp04`. **Critical State**. Must be backed up. Contains routing rules and potentially tunnel ID.
- **Logs**: Docker `json-file` driver. `/var/lib/docker/containers/<id>/<id>-json.log`. Rotation: `50m` max-size, `3` max-files.
- **In-memory state**: Connection state to Cloudflare edge (lost on restart).
- **External state**: None (Token is static secret).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ~1-2% | >10% sustained | N/A (Single core usage) |
| Memory | ~50-100MB | >250MB | OOM Kill |
| Disk I/O | Negligible (Logs) | >100MB/s | N/A |
| Network | Variable (Traffic dependent) | >1Gbps (Unlikely) | TCP backpressure |
| Request latency p50 / p95 / p99 | ~50ms / 150ms / 300ms (Edge dependent) | >1s | Timeout |
| Request rate | Low (Homelab traffic) | >10k