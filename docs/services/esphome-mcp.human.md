

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | 1 hour (IoT control degraded, not critical infrastructure) |
| **Blast radius if down** | LiteLLM loses ESPHome tools → AI assistants cannot query/config ESP devices |
| **Recovery time today** | Auto-restart (`unless-stopped`) |
| **Owner** | `phase-1.4-bulk-backfill` (automated) |

## What this service actually does

`esphome-mcp` proxies LLM requests to the ESPHome API. It enables text-based control of ESPHome devices (sensors, switches, flashing) via the Model Context Protocol.

- **Primary purpose:** Expose ESPHome management APIs to the AI fleet (LiteLLM) securely.
- **Consumer pattern:** HTTP JSON-RPC from LiteLLM; HTTP GET/POST to ESPHome backend (`DOCKP04_IP:6052`).
- **Not used for:** Direct device flashing over local Wi-Fi (requires local network access), or real-time telemetry streaming (stateless polling only).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (`./esphome` context), no registry tag |
| **Pinning policy** | Build context (rebuild required for updates) |
| **Resource caps** | None defined |
| **Volumes** | `./shared:/app/shared:ro` (read-only config) |
| **Networks** | `ai-mcp` (isolated from public/external) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | Not defined in compose |

### Configuration shape

Environment variables injected via `x-secrets-env` (`ADMIN_API_URL`, `MCP_API_KEY`, etc.) plus service-specific `ESPHOME_URL`. `ESPHOME_URL` defaults to `http://192.168.20.18:6052` via `DOCKP04_IP`. Secrets fetched at startup via `SecretsProvider`.

## Dependencies

### Hard (service cannot start or operate without these)
- **ESPHome API** (`DOCKP04_IP:6052`) — Upstream backend. If down, MCP returns 502/504.
- **SecretsProvider** — Required for `MCP_API_KEY`. Failure causes container crash at startup.
- **LiteLLM** — Upstream consumer. No direct dependency, but service is useless without it.

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI tool calls. Loss of `esphome-mcp` removes IoT tools from LLM context.

## State & persistence

- **Database tables / schemas:** None.
- **Filesystem state:** Read-only `./shared` volume. No writes.
- **In-memory state:** Connection pools to ESPHome API. Lost on restart.
- **External state (S3, etc.):** None.
- **Persistence strategy:** Stateless. Safe to redeploy frequently.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (idle polling) | > 50% sustained | N/A |
| Memory | < 256MB | > 512MB | OOM kill |
| Disk I/O | Negligible (logs only) | High write rate | Log rotation triggers |
| Network | Low (JSON-RPC) | > 10 Mbps | Timeout |
| GPU | N/A | N/A | N/A |
| Request latency p50 | < 100ms | > 1s | Timeout |
| Request rate | < 10 req/min | > 100 req/min | Throttle |

## Failure modes

- **Symptom:** LiteLLM logs "tool call failed: 502 Bad Gateway".
  - **Root cause:** ESPHome API (`DOCKP04_IP:6052`) unreachable or auth mismatch.
  - **Mitigation:** Restart container; verify `DOCKP04_IP` routing.
  - **Prevention:** Health check on backend reachability at startup.

- **Symptom:** Container restart loop at boot.
  - **Root cause:** Secrets fetch failure (Admin API/1Password Connect unreachable).
  - **Mitigation:** Check `ADMIN_API_URL` connectivity; validate tokens.
  - **Prevention:** Retry logic in `SecretsProvider`.

- **Symptom:** High memory usage.
  - **Root cause:** Leaky connection pool to ESPHome.
  - **Mitigation:** Restart container.
  - **Prevention:** Connection pooling limits in code.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless). Can run multiple instances on different hosts.
- **Coordination requirements:** None. No leader election needed.
- **State sharing across replicas:** None. Each instance maintains independent TCP connections to ESPHome backend.
- **Hardware bindings:** None. No USB/PCI passthrough required.
- **Network constraints:**
  - Must attach to `ai-mcp` network (LiteLLM connectivity).
  - Must have egress to `DOCKP04_IP:6052` (ESPHome backend).
  - Cannot expose ports externally (security isolation).
- **Cluster size constraints:** No quorum required. Single instance sufficient for current load.
- **Migration cost:** Low. Rebuild image + redeploy. Backend dependency (`DOCKP04`) remains static.
- **Scaling limit:** Bounded by ESPHome API connection limits (not container limits).

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (`last_seen`: `2026-05-01`).

### Recurring drift / chronic issues
- `DOCKP04_IP` variable drift: If `DOCKP04` moves, `ESPHOME_URL` breaks unless env file updated.

### Known sharp edges
- **SSL Verification:** `SPLUNK_VERIFY_SSL` pattern suggests some services disable SSL. Verify `ESPHOME_URL` uses valid certs if `https`.
- **Build Context:** Local build means CI/CD pipeline required for updates; no auto-pull.

## Open questions for Architect

- ? Should `esphome-mcp` move to a pre-built image registry for reproducibility?
- ? Is `DOCKP04` the permanent backend, or should it point to a HA ESPHome cluster?
- ? Does `SecretsProvider` fallback to env vars on startup failure, or hard fail?

## Reference

- Compose: `homelab-automation/stacks/mcp-servers/docker-compose.yml`
- Logs: `/var/lib/docker/containers/<id>/<id>-json.log` (json-file, 10m/3 files)
- Dashboards: Netdata `esphome-mcp` (if available via Netdata MCP)
-