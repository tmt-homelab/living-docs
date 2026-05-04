

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Minutes (AI search degradation acceptable) |
| **Blast radius if down** | LiteLLM search tools fail; AI models cannot query web via SearXNG |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual redeploy for config changes |
| **Owner** | ? (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Wraps SearXNG as an MCP server for AI model integration. Allows LiteLLM to pass search queries through to the SearXNG instance at `https://search.themillertribe-int.org`.

- **Primary purpose:** Provide authenticated, rate-limited web search capability to the AI fleet via the MCP protocol.
- **Consumer pattern:** HTTP API (MCP JSON-RPC) from LiteLLM gateway over `ai-mcp` network.
- **Not used for:** Direct user search (no UI), indexing, or caching (stateless proxy).
- **Note:** Unlike other MCP servers, it requires external network resolution capabilities via `ai-services` network join.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `Local build (./searxng context)` |
| **Pinning policy** | None (local build context, volatile) |
| **Resource caps** | ? (not specified in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only shared config) |
| **Networks** | `ai-mcp`, `ai-services` (exception to fleet isolation rule) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | None defined in compose |

### Configuration shape

- **Env vars:** `SEARXNG_URL`, `MCP_API_KEY`, plus shared secrets (`ADMIN_API_URL`, `OP_CONNECT_TOKEN`).
- **Secrets:** Fetched at container startup via `SecretsProvider` (Admin API or 1Password Connect).
- **Config surface:** Static URL binding. No runtime config reload.

## Dependencies

### Hard (service cannot start or operate without these)
- **LiteLLM** — Sole entry point for requests; without it, container idle.
- **SearXNG (`search.themillertribe-int.org`)** — Upstream search backend; if unreachable, MCP returns errors.
- **SecretsProvider** — Required at startup to resolve `MCP_API_KEY`.
- **DNS (`ai-services` network)** — Required to resolve `search.themillertribe-int.org`.

### Soft (degrade if these are down, but service still functional)
- **Admin API** — Used for secret fallback; service may start with cached/env vars if unavailable.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI search tool calls here. Total blackout on web search for AI fleet if down.

## State & persistence

- **Database tables / schemas:** None.
- **Filesystem state:** None writable (`./shared` is read-only).
- **In-memory state:** Connection pools to upstream SearXNG. Lost on restart.
- **External state:** None.
- **Backup requirement:** None (stateless).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | None | ? | ? |
| Network | Low (proxy traffic) | ? | ? |
| GPU (if applicable) | None | N/A | N/A |
| Request latency p50 / p95 / p99 | ? (depends on upstream) | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom:** LiteLLM logs `MCP server unreachable` or `502 Bad Gateway`.
- **Root cause:** Upstream SearXNG `https://search.themillertribe-int.org` down or DNS resolution failure on `tmtdockp01`.
- **Mitigation:** Verify upstream status, check `ai-services` network connectivity.
- **Prevention:** Add healthcheck to compose (currently missing).

- **Symptom:** Container restarts loop at startup.
- **Root cause:** Secrets fetch failure (Admin API/1Password down).
- **Mitigation:** Check SecretsProvider logs, fallback to env vars if configured.
- **Prevention:** Hardening SecretsProvider retry logic.

- **Symptom:** Auth errors on search requests.
- **Root cause:** `MCP_API_KEY` rotation mismatch between LiteLLM and searxng-mcp.
- **Mitigation:** Restart container to fetch new secret.
- **Prevention:** Automated secret rotation with zero-downtime rollout.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless).
- **Coordination requirements:** None (no leader election needed).
- **State sharing across replicas:** None (if multiple instances exist, they share no state).
- **Hardware bindings:** None.
- **Network constraints:**
    - **Critical Exception:** Must join `ai-services` network to resolve upstream hostname. Violates fleet-wide `ai-mcp` only isolation rule.
    - **Port binding:** None (internal container port only).
- **Cluster size constraints:** Currently single instance (`tmtdockp01`). Can scale horizontally if upstream SearXNG supports load balancing.
- **Migration cost:** Low (stateless). Network config change required to remove `ai-services` dependency if upstream moves.
- **Secrets dependency:** Secrets fetched at *startup* only. Rolling update requires container restart to pick up new keys.
- **Build dependency:** Local build context (`./searxng`). CI/CD pipeline required to push to registry for fleet-wide deployment.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB.

### Recurring drift / chronic issues
- ?

### Known sharp edges
- **Network Isolation:** Breaking the `ai-mcp` only rule (joining `ai-services`) complicates firewall auditing and lateral movement detection.
- **Secrets Fetch:** If SecretsProvider is slow, container startup time increases. No liveness probe defined to catch stuck startup.
- **Upstream URL:** `SEARXNG_URL` is hardcoded in compose env. Changing upstream requires compose change + redeploy.

## Open questions for Architect

- Why does this service require `ai-services` network access while others use `ai-mcp` + host IP routing?
- Should `SE