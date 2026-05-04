

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Minutes (media stats are non-critical for core infrastructure) |
| **Blast radius if down** | LiteLLM loses Tautulli tool access; AI assistants cannot query Plex watch history or server health via Tautulli |
| **Recovery time today** | Auto-restart (`unless-stopped`) via Docker daemon |
| **Owner** | `?` (CMDB `registered_by`: `phase-1.4-bulk-backfill`) |

## What this service actually does

`tautulli-mcp` is a Model Context Protocol (MCP) server that exposes Tautulli analytics to AI models via the `ai-mcp` network. It acts as a read-only proxy for Plex server statistics, user activity, and media consumption trends.

The fleet uses it when an LLM needs context about homelab media usage (e.g., "Who watched the latest episode?"). It does not host media, transcode video, or manage Plex directly. It strictly queries the Tautulli API and returns JSON to the MCP client.

It is NOT used for media playback, direct Plex administration, or alerting. It is a data retrieval endpoint for the AI orchestration layer (LiteLLM).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `Local build (context ./tautulli)` |
| **Pinning policy** | None (local build context; no registry digest) |
| **Resource caps** | Unknown (no `deploy.resources` defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config) |
| **Networks** | `ai-mcp` (external Docker bridge) |
| **Secrets** | `services/tautulli/api_key`, `services/readonly-shared/mcp_api_key` (1Password Connect) |
| **Healthcheck** | None defined in compose |

### Configuration shape

Configuration is driven by environment variables injected at startup. The `SecretsProvider` python module fetches secrets from 1Password Connect or Admin API before the app starts.
- `TAUTULLI_URL`: `http://${DOCKP04_IP}:8181` (Backend location)
- `MCP_API_KEY`: Auth token for incoming MCP connections.
- No persistent YAML config files inside the container; all stateless.

## Dependencies

### Hard (service cannot start or operate without these)
- **admin-api-mcp** — Required for `SecretsProvider` to fetch `TAUTULLI_API_KEY` and `MCP_API_KEY` at boot.
- **tautulli** (backend) — Required for data retrieval at `DOCKP04_IP:8181`.
- **1Password Connect / Admin API** — Required for secret resolution (fallback chain defined in code).

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI requests to this MCP container via `ai-mcp` network.
- **AI Clients** — Any model enabled for `tautulli` tools.

## State & persistence

This service is fully stateless.
- **Database tables:** None.
- **Filesystem state:** None writable. `./shared` is mounted read-only.
- **In-memory state:** Connection caches to Tautulli backend (lost on restart).
- **External state:** None. Logs are ephemeral (`json-file`, 10m max size).

**Backup requirement:** None. Re-deployable from compose file.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% (idle) | > 50% sustained | N/A |
| Memory | < 50MB | > 200MB | OOM kill (no limit set) |
| Disk I/O | Negligible | N/A | N/A |
| Network | Sporadic (on AI query) | > 10MB/s sustained | TCP backlog |
| Request latency p50 | < 200ms (to Tautulli) | > 2s | Timeout |
| Request rate | < 10 req/min | > 100 req/min | Rate limit (Tautulli) |

## Failure modes

- **Secrets Fetch Failure**
    - *Symptom:* Container exits immediately on startup.
    - *Root cause:* Admin API or 1Password unreachable.
    - *Mitigation:* Check `ADMIN_API_URL` env var and network connectivity to `DOCKP04`.
- **Tautulli Backend Unreachable**
    - *Symptom:* MCP returns 503/Timeout to AI.
    - *Root cause:* `DOCKP04_IP` changes or Tautulli service down.
    - *Mitigation:* Restart container to re-resolve env