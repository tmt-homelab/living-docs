

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Minutes (non-critical, `critical: false`) |
| **Blast radius if down** | AI assistants lose ability to query/modify UniFi Network Controller devices. Automation scripts fail. |
| **Recovery time today** | Auto-restart (`unless-stopped`) via Docker daemon. Manual intervention if secrets rotate. |
| **Owner** | `phase-1.4-bulk-backfill` (automation) / `?` (human steward) |

## What this service actually does

Proxy for AI models to access the UniFi Network Controller API. It translates LLM tool calls into UniFi API requests (device status, network stats, config changes).

- **Primary purpose:** Read/Write access to UniFi Network Controller (UDM/USG/USW) via the MCP protocol.
- **Consumer pattern:** HTTP API (LiteLLM gateway on `ai-mcp` network) → `unifi-mcp` container → UniFi Controller HTTPS API.
- **Not used for:** UniFi Protect (cameras) is handled by `unifi-protect-mcp`. General network management UI tasks are handled by `unifi-network-mcp`. This service focuses on the core Network Controller API.
- **Auth:** Validates incoming requests via `MCP_API_KEY`. Authenticates outgoing UniFi requests via `username`/`password` fetched from 1Password.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (`./unifi` context) — no remote tag |
| **Pinning policy** | None (local build context) |
| **Resource caps** | None defined (unbounded) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config/scripts) |
| **Networks** | `ai-mcp` (external bridge) |
| **Secrets** | `services/unifi/username`, `services/unifi/password`, `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | None defined in compose |

### Configuration shape

Environment variables injected via `x-secrets-env` and specific overrides:
- `UNIFI_HOST`: Target controller hostname/IP (env var, value unknown).
- `UNIFI_PORT`: "443" (HTTPS).
- `UNIFI_SITE`: "default".
- `UNIFI_VERIFY_SSL`: "false" (Self-signed cert accepted).
- `MCP_API_KEY`: Shared auth token for incoming MCP requests.

## Dependencies

### Hard (service cannot start or operate without these)
- **UniFi Controller**: API endpoint defined by `UNIFI_HOST`. If down, service returns 503/timeout.
- **SecretsProvider (1Password Connect/Admin API)**: Required at startup to fetch credentials.
- **LiteLLM Gateway**: Only entry point via `ai-mcp` network.

### Soft (degrade if these are down, but service still functional)
- **None**: No other internal homelab services required for basic operation.

### Reverse (services that depend on THIS service)
- **LiteLLM**: Routes AI tool requests to this service. If down, AI cannot manage network devices.
- **Automation Scripts**: Any external scripts calling MCP directly (rare, usually via LiteLLM).

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**: None writable. `./shared` is mounted read-only.
- **In-memory state**: Session tokens for UniFi API (lost on restart).
- **External state**: All state resides on the UniFi Controller host.
- **Backups**: N/A (Stateless).
- **RPO/RTO**: N/A (Stateless).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% | > 80% sustained | Throttles requests |
| Memory | < 100MB | > 500MB | OOM killed (no limit set) |
| Disk I/O | Negligible | N/A | N/A |
| Network | Low (polling) | High (burst) | Drops packets |
| GPU | None | N/A | N/A |
| Request latency p50 / p95 / p99 | ~200ms /