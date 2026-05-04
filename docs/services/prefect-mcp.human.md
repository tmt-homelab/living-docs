

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | `unplanned outage acceptable for ≤ 1 hour` (Critical: false) |
| **Blast radius if down** | LiteLLM cannot trigger Prefect workflows; AI assistants lose automation capability. No impact on core infrastructure or other MCPs. |
| **Recovery time today** | `auto-restart` (Docker `unless-stopped`) |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`; no human owner in CMDB) |

## What this service actually does

`prefect-mcp` acts as a stateless translation layer between AI models (via LiteLLM) and the Prefect orchestration engine. It exposes Prefect API endpoints as MCP tools, allowing LLMs to list flows, trigger runs, and inspect task status.

It does **not** run workflows itself; it does not store state. All workflow state resides in the Prefect Server (hosted on `DOCKP04`). The container is purely an HTTP proxy with authentication injection. If this container dies, the Prefect API remains up; only the AI interface to it is lost.

Other fleet services consume this via the `ai-mcp` network. LiteLLM is the sole ingress point. No direct external access to `prefect-mcp` is permitted.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local build` (context: `./prefect`) |
| **Pinning policy** | `none` (build from local context; no digest/tag in compose) |
| **Resource caps** | `?` (No `mem_limit` or `cpus` defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only shared config) |
| **Networks** | `ai-mcp` (Docker bridge, isolated) |
| **Secrets** | 1Password paths: `services/prefect-mcp/mcp_api_key`, `services/prefect/api_key` |
| **Healthcheck** | `?` (Not defined in compose snippet) |

### Configuration shape

Environment variables are injected via `secrets_env` anchor (Admin API, 1Password Connect) + specific overrides (`PREFECT_URL`).
*   `PREFECT_URL`: `http://${DOCKP04_IP}:4200` (Target Prefect Server)
*   `MCP_API_KEY`: Fetched from 1Password (`services/prefect-mcp/mcp_api_key`).
*   `ADMIN_API_TOKEN`: Fetched from 1Password.
*   No local config files; all config is env-driven.

## Dependencies

### Hard (service cannot start or operate without these)
- **Prefect API** (`DOCKP04_IP:4200`) — Without this, the MCP returns 502/503 on all tool calls.
- **Secrets Provider** (Admin API / 1Password Connect) — Container startup fails if secrets cannot be fetched (per `SecretsProvider` logic in shared code).
- **LiteLLM** — No other service routes traffic here; if LiteLLM is down, this service is idle but healthy.

### Soft (degrade if these are down, but service still functional)
- **None** — The container itself does not degrade without external dependencies; it either connects or fails.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Uses this to expose Prefect tools to LLMs. If down, AI automation workflows are unavailable.

## State & persistence

- **Database tables / schemas**: `none` (State lives in Prefect Server DB on `DOCKP04`).
- **Filesystem state**: `none`. Mounts `./shared` read-only. No writable local storage.
- **In-memory state**: `ephemeral`. HTTP session state only. Lost on restart.
- **External state**: `1Password Connect` (for secrets), `Prefect Server` (for workflow state).
- **RPO/RTO**: N/A (Stateless). RTO = container restart time (< 1 min).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | `?` (Idle mostly) | `?` | `?` |
| Memory | `?` | `?` | `?` |
| Disk I/O | `Negligible` (logs only) | `?` | `?` |
| Network | `Low` (burst on workflow triggers) | `?` | `?` |
| GPU (if applicable) | `0` | `?` | `?` |
| Request latency p50 / p95 / p99 | `?` | `?` | `?` |
| Request rate | `Low` (Intermittent AI calls) | `?` | `?` |

## Failure modes

- **Symptom**: LiteLLM returns "MCP server unavailable" for Prefect tools.
- **Root cause**: Prefect API (`DOCKP04`) unreachable or 1Password secret rotation not picked up.
- **Mitigation**: Check container logs (`docker logs prefect-mcp`). Restart container if secrets cache is stale.
- **Prevention**: Add container healthcheck to probe `PREFECT_URL`.

- **Symptom**: Container restarts loop.
- **