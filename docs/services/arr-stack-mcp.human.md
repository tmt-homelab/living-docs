

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical media ops) |
| **Blast radius if down** | LiteLLM cannot execute media management tools (add/remove movies, queue checks). User AI agents fail on `arr_stack` tool calls. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Manual rebuild if `./arr-stack` context changes. |
| **Owner** | ? (Human), `phase-1.4-bulk-backfill` (Agent ID) |

## What this service actually does

`arr-stack-mcp` acts as a middleware gateway between the AI fleet (LiteLLM) and the media automation stack (Sonarr/Radarr/Prowlarr). It exposes read/write capabilities of the Arr suite to LLMs via the MCP protocol.

It receives JSON-RPC requests from LiteLLM over the `ai-mcp` network, authenticates them via `MCP_API_KEY`, and proxies requests to the backend APIs hosted on `DOCKP04`. It handles schema mapping for the LLM (e.g., translating "add movie" to Radarr API `POST /api/v3/movie`).

It is **NOT** a storage backend. It does not download media. It does not host a web UI. It does not persist local state other than transient logs. It is **NOT** used for direct user login or authentication (relies on backend API tokens).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build (./arr-stack)` |
| **Pinning policy** | `none` (local build context; no digest/tag enforced) |
| **Resource caps** | `?` (Not defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config/scripts) |
| **Networks** | `ai-mcp` (internal bridge), `host` (for outbound to DOCKP04 via IP) |
| **Secrets** | 1Password Connect: `services/arr-stack-mcp/mcp_api_key`, `services/radarr/api_key`, `services/sonarr/api_key`, `services/prowlarr/api_key` |
| **Healthcheck** | `?` (Not defined in compose) |

### Configuration shape

Environment variables drive connectivity. `ADMIN_API_URL` and `MCP_API_KEY` inherited from `x-secrets-env`. Target services defined via `RADARR_URL` (`http://${DOCKP04_IP}:7878`), `SONARR_URL` (`8989`), `PROWLARR_URL` (`9696`). All backend IPs resolved via `DOCKP04_IP` env var injected at deploy time.

## Dependencies

### Hard (service cannot start or operate without these)
- **DOCKP04 (Radarr/Sonarr/Prowlarr)** — Core functionality. If unreachable, MCP returns 502/504 to LiteLLM.
- **1Password Connect** — Secrets fetch at startup. If timeout, container exits (startup failure).
- **LiteLLM** — Sole consumer. No traffic flows without it.

### Soft (degrade if these are down, but service still functional)
- **Admin API (dockp04:8000)** — Used for auth/audit logging. Service runs without it, but audit trail missing.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI tool calls to this service. Breaks media management tools immediately.

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**: None writable. `./shared` mounted read-only.
- **In-memory state**: Request context lost on restart. No session caching.
- **External state**: All state resides on DOCKP04 (Arr instances).
- **Logs**: `json-file` driver. `max-size: 10m`, `max-file: 3`. Retention: ~30MB max per instance.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (idle) | > 50% sustained | Queues requests, eventual timeout |
| Memory | < 256MB | > 512MB | OOM kill if leak |
| Disk I/O | Negligible (logs only) | High write | N/A |
| Network | < 1Mbps (control) | > 100Mbps | Bandwidth limited by Arr APIs |
| Request latency p50 / p95 / p99 | 50ms / 200ms / 1s | p99 > 5s | Timeout errors to LiteLLM |
| Request rate | < 10 req/min | > 100 req/min | Rate limit on backend APIs |

## Failure modes

- **Symptom**: LiteLLM returns "Tool execution failed".
- **Root cause**: `DOCKP04_IP` env var mismatch or DOCKP04 firewall drop.
- **Mitigation**: Check `docker logs arr-stack-mcp`. Verify `ADMIN_API_URL` connectivity.
- **Prevention**: Validate `DOCKP04_IP` in deploy workflow before `compose up`.

- **Symptom**: Container exits on startup.
- **Root cause**: 1Password Connect timeout or missing secret path.
- **Mitigation**: Check `OP_CONNECT_HOST` connectivity. Verify secret paths in vault.
- **Prevention**: Add startup probe for secrets provider.

- **Symptom**: High memory usage.
- **Root cause**: Python MCP SDK leak on large JSON responses (e.g., full show list).
- **Mitigation**: Restart container.
- **Prevention**: Paginate large API responses in code.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless). Can run multiple instances for load balancing, but not currently configured.
- **Coordination requirements** None. No leader election required.
- **State sharing across replicas** None. All