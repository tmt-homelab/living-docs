

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless API wrapper) |
| **Tolerable outage** | Minutes (non-critical; AI agents retry) |
| **Blast radius if down** | AI agents lose DNS management capability (zones/records/tunnels); LiteLLM routing unaffected |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual intervention if secrets provider fails |
| **Owner** | unknown (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Acts as a Model Context Protocol (MCP) bridge for Cloudflare API operations.
- **Primary purpose:** Allows AI agents (via LiteLLM) to read/update DNS records, manage Zero Trust tunnels, and query zone settings programmatically.
- **Consumer pattern:** Receives JSON-RPC over HTTP from LiteLLM on the `ai-mcp` network. Authenticates via Bearer token (`MCP_API_KEY`).
- **Not used for:** Direct user web traffic, CDN configuration UI, or acting as a DNS resolver. It is an automation endpoint, not a gateway.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context: `./cloudflare`) |
| **Pinning policy** | Build context (requires `--build` on update) |
| **Resource caps** | None defined (defaults to host limits) |
| **Volumes** | `./shared:/app/shared:ro` (shared config read-only) |
| **Networks** | `ai-mcp` (external bridge) |
| **Secrets** | 1Password Connect: `services/cloudflare-mcp/mcp_api_key`, `services/cloudflare/api_key`, `services/cloudflare/email` |
| **Healthcheck** | None defined in compose |

### Configuration shape

Environment variables injected at startup via `SecretsProvider` (shared/secrets_provider.py).
- **Auth:** `MCP_API_KEY` (shared fleet auth), `CLOUDFLARE_API_TOKEN` (CF specific).
- **Endpoint:** Defaults to `api.cloudflare.com` (internal code logic).
- **Profiles:** Only starts if `--profile phase2` is passed to compose.

## Dependencies

### Hard (service cannot start or operate without these)
- **1Password Connect / Admin API** — SecretsProvider fails without network reachability to `DOCKP04_IP` (192.168.20.18).
- **ai-mcp network** — Container cannot resolve LiteLLM gateway without this Docker bridge.
- **LiteLLM** — Upstream consumer; no direct API usage from outside fleet.

### Soft (degrade if these are down, but service still functional)
- **Cloudflare API** — Service runs but returns 502/401 on upstream calls.

### Reverse (services that depend on THIS service)
- **AI Agents (via LiteLLM)** — Lose DNS management tools. Low impact on core homelab function.

## State & persistence

- **Database tables:** None.
- **Filesystem state:** None writable. `/app/shared` is read-only.
- **In-memory state:** API tokens cached in memory for session duration. Lost on restart.
- **External state:** Cloudflare DNS state lives in Cloudflare SaaS (not this service).
- **Logs:** `json-file`, max 10m, 3 files. Rotated locally on host `tmtdockp01`.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% | > 50% sustained | N/A |
| Memory | < 50MB | > 500MB | N/A |
| Disk I/O | Negligible | > 10MB/s | N/A |
| Network | < 100KB/s | > 10MB/s | TCP backpressure from Cloudflare API |
| Request latency p50 | 200ms | > 2s | API rate limits |
| Request rate | < 10 req/min | > 100 req/min | 429 Too Many Requests |

## Failure modes

- **Token Expiration**
  - **Symptom:** 401 Unauthorized responses in logs.
  - **Root cause:** Cloudflare API token rotated or revoked in 1Password.
  - **Mitigation:** Restart container to trigger SecretsProvider fetch.
  - **Prevention:** Automated token rotation via 1Password Connect lifecycle.

- **SecretsProvider Unreachable**
  - **Symptom:** Container fails to start / exits code 1.
  - **Root cause:** `DOCKP04_IP` (Admin API) is down or firewall blocked.
  - **Mitigation:** Restore connectivity to Admin API host.
  - **Prevention:** Health checks on Admin API dependency.

- **API Rate Limiting**
  - **Symptom:** 429 errors on bulk DNS operations.
  - **Root cause:** AI agent chaining too many requests.
  - **Mitigation:** Throttle agent tool usage.
  - **Prevention:** Implement local rate limiting in MCP server code.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless), but constrained by compose config.
- **Coordination requirements:** None. State is external (Cloudflare).
- **State sharing across replicas:** None. Multiple instances are safe if token is shared, but risk concurrent write conflicts on same DNS zone.
- **Hardware bindings:** None.
- **Network constraints:**
  - Must remain on `ai-mcp` network (Docker bridge on `tmtdockp01`).
  - Does not expose host ports (internal only).
  - Cross-host routing relies on host IP (`DOCKP04_IP`) for secrets.
- **Cluster size constraints:** Currently `container_name: cloudflare-mcp` enforces single instance per stack. Scaling requires removing `container_name` and using service discovery.
- **Migration cost:** Low. Requires updating compose to allow multiple replicas and ensuring SecretsProvider handles concurrency (it does not).
- **Failure isolation:** Single host (`tmtdockp01`). If host dies, service is down. No cross-host failover defined.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (service registered `2026-05-01`, likely new deployment).

### Recurring drift / chronic issues
- **Secrets drift:** If 1Password item path changes, container must be rebuilt/restarted.
- **Profile drift