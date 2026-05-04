

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy/adapter) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical management plane) |
| **Blast radius if down** | AI assistants lose Portainer container/stack visibility; no impact on running containers |
| **Recovery time today** | `auto-restart` (Docker `unless-stopped` + healthcheck retry) |
| **Owner** | `?` (CMDB `registered_by`: `phase-1.4-bulk-backfill`) |

## What this service actually does

Acts as a translation layer between the `LiteLLM` AI gateway and the Portainer management API. Exposes Portainer resources (containers, stacks, networks) as MCP tools for AI models to inspect or modify.

- **Primary purpose:** Enable AI-driven infrastructure management via Portainer API.
- **Consumer pattern:** HTTP API (incoming from LiteLLM on `ai-mcp` network; outgoing to Portainer on `DOCKP02_IP:9001`).
- **What it is NOT:** Not a standalone container manager. Does not host the Portainer UI. `PORTAINER_ENABLE_STACK_OPS` is disabled, limiting AI actions to read/modify existing containers rather than deploying stacks.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (`context: ./portainer`) — no external registry tag |
| **Pinning policy** | None (local Dockerfile build) |
| **Resource caps** | None defined in compose |
| **Volumes** | `./shared:/app/shared:ro` (shared config; read-only) |
| **Networks** | `ai-mcp` (external bridge) |
| **Secrets** | 1Password paths: `services/portainer-mcp/mcp_api_key`, `services/portainer/api_token` |
| **Healthcheck** | None defined (relies on Docker restart policy) |

### Configuration shape

Configuration is injected via environment variables resolved at startup.
- **Secrets Provider:** Fetches `MCP_API_KEY` and `PORTAINER_API_KEY` from 1Password via `Admin API` or `1Password Connect`.
- **Target Resolution:** `PORTAINER_URL` resolves `https://${DOCKP02_IP}:9001`.
- **Scope Control:** `PORTAINER_ENABLE_STACK_OPS: "false"` explicitly disables stack deployment tools.
- **Env File:** `DOCKP02_IP` must be provided via `--env-file` during `docker compose up`; defaults are not set for this variable in the snippet.

## Dependencies

### Hard (service cannot start or operate without these)
- **Portainer Instance** — `DOCKP02_IP:9001`. If unreachable, all MCP tools fail immediately.
- **Secrets Provider** — `Admin API` or `1Password Connect`. Startup hangs or fails without valid `MCP_API_KEY` and `PORTAINER_API_KEY`.
- **LiteLLM Gateway** — `ai-mcp` network isolation. No external ingress; must receive traffic from LiteLLM.

### Soft (degrade if these are down, but service still functional)
- **ADMIN_API** — Fallback to direct 1Password Connect if Admin API is down (per `SecretsProvider` logic).

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI requests to this endpoint.
- **AI Assistants** — Lose infrastructure management capabilities if this service is down.

## State & persistence

- **Database tables / schemas:** None (stateless).
- **Filesystem state:** None writable. `./shared` volume is read-only (`:ro`).
- **In-memory state:** API keys and connection tokens held in RAM only. Lost on restart.
- **External state:** Portainer state resides on `DOCKP02` (separate host/service).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (< 5%) | > 50% sustained | Drops requests if API timeout |
| Memory | Low (< 200MB) | > 500MB | OOM killed by Docker (no limits set) |
| Disk I/O | Negligible | N/A | N/A |
| Network | Bursty (request/response) | > 100MB/s | Throttled by upstream Portainer |
| Request latency p50 | < 200ms | > 2s | Timeout error returned to AI |
| Request rate | Low (intermittent) | > 100 req/min | Rate limited by Portainer API |

## Failure modes

- **Symptom:** `401 Unauthorized` from LiteLLM.
  - **Root cause:** `PORTAINER_API_KEY` rotated or expired in 1Password; MCP service not updated.
  - **Mitigation:** Restart container to fetch new secrets from SecretsProvider.
  - **Prevention:** Automated secret rotation workflow (not currently implemented).

- **Symptom:** `Connection Refused` to `DOCKP02_IP:9001`.
  - **Root cause:** `DOCKP02_IP` env var missing or Portainer instance down.
  - **Mitigation:** Verify `DOCKP02_IP` in deploy env-file; check Portainer health.
  - **Prevention:** Add dependency check in startup script.

- **Symptom:** Tools appear but fail on execution.
  - **Root cause:** `PORTAINER_ENABLE_STACK_OPS: "false"` blocking specific actions.
  - **Mitigation:** Enable flag if required (requires security review).
  - **Prevention:** Document capability limitations in AI system prompt.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless), but constrained by single Portainer target.
- **Coordination requirements:** None. No leader election needed.
- **State sharing across replicas:** None. Each instance fetches secrets independently.
- **Hardware bindings:** None.
- **Network constraints:**
  - Must reside on `ai-mcp` network.
  - Outbound access required to `DOCKP02_IP:9001` (HTTPS).
  - Inbound access restricted to LiteLLM (via `ai-mcp` isolation).
- **Cluster size constraints:** Single instance per host logic (CMDB record `portainer-mcp` exists once). Running multiple instances against same Portainer API could cause race conditions on write operations (e.g., container tagging).
- **Migration cost:** Low. Swap `DOCKP02_IP` to new host IP in env-file; restart.
- **Constraint:** `PORTAINER_ENABLE_STACK_OPS: "false"` is a hard capability limit. Changing this exposes stack deployment risks (potential for destructive operations by AI).
- **Constraint:** `DOCKP02_IP` is a variable, not a DNS name. DNS-based failover over `DOCKP02_IP` is impossible without variable change.

## Operational history

### Recent incidents (last 90 days)
- None recorded. CMDB `last_seen`: `2026-05-01T