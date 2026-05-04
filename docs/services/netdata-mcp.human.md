

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical monitoring channel) |
| **Blast radius if down** | LiteLLM AI models lose access to host metrics (`tmtdockp01`). Debugging operations degrade; AI cannot query system health via MCP. |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual intervention if host network unreachable |
| **Owner** | ? (registered_by: phase-1.4-bulk-backfill) |

## What this service actually does

Bridges the Model Context Protocol (MCP) to the Netdata monitoring instance running on the host (`tmtdockp01`). Allows AI assistants (via LiteLLM gateway) to programmatically query system resources, alerts, and health metrics.

- **Primary purpose:** Expose Netdata API (port 19999) to the `ai-mcp` network as an MCP server.
- **Consumer pattern:** HTTP API (MCP JSON-RPC) from LiteLLM; HTTP GET/POST to Netdata backend.
- **NOT used for:** Direct dashboard visualization, log aggregation, or alerting. It is a read-only telemetry channel for AI agents.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (context `./netdata`) — no registry tag pinned |
| **Pinning policy** | Build context (digest unknown); rebuilds on `docker compose up --build` |
| **Resource caps** | None defined (unlimited CPU/Mem) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config) |
| **Networks** | `ai-mcp` (external Docker bridge) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | None defined in compose |

### Configuration shape

Environment variables resolved at startup via `SecretsProvider` + Compose interpolation. `NETDATA_URL` targets the host IP variable `${DOCKP01_IP}` (defaults to `192.168.20.18` locally, set via `--env-file` in production). `MCP_API_KEY` validates inbound requests. No persistent config files written inside container.

## Dependencies

### Hard (service cannot start or operate without these)
- **Netdata instance (Host `tmtdockp01`)** — API endpoint `http://${DOCKP01_IP}:19999`. If host network is isolated or Netdata process dies, this service returns 502/timeout to consumers.
- **LiteLLM Gateway** — Upstream client. If LiteLLM is down, this service sits idle (no blast radius upstream).

### Soft (degrade if these are down, but service still functional)
- **Admin API (dockp04)** — Required for `SecretsProvider` to fetch `MCP_API_KEY` on startup. If down, container fails to start (secrets missing).
- **1Password Connect** — Fallback for secrets. If Admin API unreachable, service relies on OP Connect env vars.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI requests to this MCP server.
- **AI Assistants** — Indirect consumers querying metrics for diagnostics.

## State & persistence

- **Database tables / schemas:** None (stateless container).
- **Filesystem state:** None writable. `./shared` volume is read-only (`:ro`).
- **In-memory state:** Request cache / connection pools lost on restart.
- **External state:** Netdata metrics reside on host `tmtdockp01` (Netdata DB/Cache).
- **RPO/RTO:** RPO 0 (no local state). RTO < 2 mins (container restart).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (idle) | > 50% sustained | Throttled by host cgroups |
| Memory | < 50MB | > 200MB | OOM kill (no limit set) |
| Disk I/O | Minimal | N/A | N/A |
| Network | Low (API calls) | High volume (DDoS risk) | Connection refused (no rate limit) |
| Request latency p50 | < 100ms | > 2s | Timeout |
| Request rate | < 10 req/min | > 100 req/min | Netdata API rate limit |

## Failure modes

- **Symptom:** `502 Bad Gateway` from LiteLLM to AI.
    - **Root cause:** `NETDATA_URL` unreachable (host firewall, Netdata crash, IP mismatch).
    - **Mitigation:** Check `tmtdockp01` Netdata status. Verify `DOCKP01_IP` env var.
    - **Prevention:** Add container healthcheck pinging Netdata URL.
- **Symptom:** Container restart loop.
    - **Root cause:** Secrets fetch failure (Admin API down).
    - **Mitigation:** Check `ADMIN_API_URL` connectivity.
    - **Prevention:** Retry logic in SecretsProvider (already present).
- **Symptom:** AI model hallucinates metrics.
    - **Root cause:** Netdata API schema change / MCP parser mismatch.
    - **Mitigation:** Rebuild container (`./netdata` context).
    - **Prevention:** Pin Netdata API version in Dockerfile.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless), but **not recommended** without Netdata replication.
- **Coordination requirements:** None. Stateless proxy.
- **State sharing across replicas:** None. Each instance connects to the configured `NETDATA_URL`.
- **Hardware bindings:** None. Runs on standard x86_64 Docker host.
- **Network constraints:**
    - **Inbound:** Only from `ai-mcp` network (LiteLLM).
    - **Outbound:** Must reach `tmtdockp01` on port 19999.
    - **Constraint:** `NETDATA_URL` is bound to a specific host IP variable (`DOCKP01_IP`). Moving this container to another host (`dockp02`) requires changing the env var to point to `tmtdockp0