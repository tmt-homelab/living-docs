

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | `unplanned outage acceptable for ≤ 1 hour` (non-critical media requests) |
| **Blast radius if down** | `LiteLLM stops routing → AI assistants cannot check media availability or approve requests` |
| **Recovery time today** | `auto-restart` (docker `unless-stopped`) |
| **Owner** | `?` (registered_by: phase-1.4-bulk-backfill) |

## What this service actually does

Proxy layer exposing Overseerr media management API to the AI fleet via Model Context Protocol (MCP). It translates LLM tool calls into Overseerr API requests (check status, approve requests) and returns structured JSON to LiteLLM.

It is NOT a media server, database, or file storage. It holds no persistent state locally. All media metadata, request queues, and user data reside in the upstream Overseerr instance (`http://DOCKP04_IP:5055`).

Consumers: `LiteLLM` (gateway) connects to this service over the `ai-mcp` Docker network. It does not expose ports to the host network or public internet.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `build: ./overseerr` (local build context, no registry tag) |
| **Pinning policy** | `none` (built from local Dockerfile at deploy time) |
| **Resource caps** | `?` (no limits defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config share) |
| **Networks** | `ai-mcp` (isolated Docker bridge) |
| **Secrets** | `1Password Connect`: `services/overseerr-mcp/mcp_api_key`, `services/overseerr/api_key` |
| **Healthcheck** | `?` (not defined in compose) |

### Configuration shape

Environment variables are injected via `x-secrets-env` and specific overrides (`OVERSEERR_URL`). `SecretsProvider` fetches tokens at container startup from Admin API or 1Password Connect. No YAML/JSON config files mounted; configuration is ephemeral per container lifecycle.

## Dependencies

### Hard (service cannot start or operate without these)
- `DOCKP04_IP` resolution — upstream Overseerr backend API. If unreachable, service starts but fails all tool calls.
- `MCP_API_KEY` — Bearer token validation for incoming requests from LiteLLM.
- `OVERSEERR_API_KEY` — Authentication for outgoing requests to Overseerr backend.

### Soft (degrade if these are down, but service still functional)
- `SecretsProvider` — If Admin API is down, falls back to 1Password Connect. If both fail, container exits or starts with missing creds.

### Reverse (services that depend on THIS service)
- `LiteLLM` — Routes AI tool calls to this endpoint. If down, AI assistants lose media request capability.

## State & persistence

- **Database tables**: None (stateless proxy).
- **Filesystem state**: `/app/shared` (read-only mount). No writable volumes.
- **In-memory state**: Request context, auth tokens (cached in memory until container restart).
- **External state**: All data resides in Overseerr backend (`http://DOCKP04_IP:5055`).
- **Logs**: `json-file`, `10m` max-size, `3` files (30MB total retention per container).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | `?` | `?` | `?` |
| Memory | `?` | `?` | `?` |
| Disk I/O | `low` (logs only) | `?` | `?` |
| Network | `low` (HTTP/JSON) | `?` | `?` |
| GPU | `N/A` | `N/A` | `N/A` |
| Request latency p50 / p95 / p99 | `?` | `?` | `?` |
| Request rate | `?` | `?` | `?` |

## Failure modes

- **Symptom**: `LiteLLM logs: "MCP server unreachable"`.
  - **Root cause**: `overseerr-mcp` container exited or `DOCKP04_IP` routing broken.
  - **Mitigation**: `docker compose