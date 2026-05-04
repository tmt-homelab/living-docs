

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Hours (CMDB `critical: false`) |
| **Blast radius if down** | AI assistants lose homelab management capability; LiteLLM routing unaffected |
| **Recovery time today** | Auto-restart (`unless-stopped`) |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Acts as an MCP server proxying requests from the AI fleet (via LiteLLM) to the internal `admin-api` service. It authenticates incoming MCP requests using `MCP_API_KEY` and forwards authorized calls to the Admin API on `DOCKP04_IP:8000`.

It is not a standalone admin interface. It does not store state locally. It exists solely to enable LLMs to execute administrative actions (create/delete resources, query status) through the Model Context Protocol. If `admin-api` is unreachable, this container runs but returns 5xx to the AI client.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build ./admin-api` (no remote tag) |
| **Pinning policy** | Build context (requires `--build` on changes) |
| **Resource caps** | ? (No limits defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config/shared) |
| **Networks** | `ai-mcp` (external bridge) |
| **Secrets** | `ADMIN_API_TOKEN`, `MCP_API_KEY` (via SecretsProvider/1Password) |
| **Healthcheck** | None (Docker relies on exit code) |
| **Profile** | `phase1` |

### Configuration shape

Configuration is injected via environment variables at container start. `ADMIN_API_URL` points to `http://192.168.20.18:8000` (default). `MCP_API_KEY` validates incoming requests. Secrets are resolved via `SecretsProvider` before the service starts. No YAML config files are mounted.

## Dependencies

### Hard
- `admin-api` (`192.168.20.18:8000`) — Core backend. If down, this service returns errors to AI clients.
- `SecretsProvider` — Required to fetch `ADMIN_API_TOKEN` and `MCP_API_KEY`.
- `ai-mcp` network — Isolated Docker bridge; cannot operate without connectivity to LiteLLM.

### Soft
- None.

### Reverse
- `LiteLLM` — Routes MCP requests to this container.
- `AI Assistants` — Consume management tools exposed via this MCP server.

## State & persistence

- **Database tables:** None.
- **Filesystem state:** `./shared` mount is read-only. No local writes.
- **In-memory state:** Request context only (lost on restart).
- **External state:** Relies on `admin-api` for state persistence.
- **Backup:** Not applicable (stateless).
- **RPO/RTO:** N/A for data; RTO = container restart time (~5s).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 50% sustained | ? |
| Memory | < 128MB | > 512MB | ? |
| Disk I/O | Negligible | N/A | N/A |
| Network | Low (internal) | > 100MB/s | ? |
| Request latency p50 | < 200ms | > 1s | Queue buildup |
| Request rate | < 10 req/s | > 50 req/s | ? |

## Failure modes

- **Symptom:** AI assistants report "Tool execution failed" or "500 Internal Server Error".
- **Root cause:** `admin-api` unreachable on `DOCKP04_IP`, or `MCP_API_KEY` rotation mismatch.
- **Mitigation:** Check `docker logs admin-api-mcp`. Verify `ADMIN_API_URL` connectivity from container.
- **Prevention:** Health checks on `admin-api` upstream. Secrets rotation workflow validation.

- **Symptom:** Container fails to start.
- **Root cause:** Secrets fetch failure (`SecretsProvider` error).
- **Mitigation:** Verify 1Password Connect tokens and `ADMIN_API_TOKEN` validity.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless proxy).
- **Coordination requirements:** None (no leader election).
- **State sharing across replicas:** None.
- **Hardware bindings:** None.
- **Network constraints:** Must reside on `ai-mcp` network. Cannot expose ports externally.
- **Cluster size constraints:** None (limited by `admin-api` concurrency capacity).
- **Migration cost:** Low (copy container config/env).
- **Backend dependency:** Single `admin-api` instance on `dockp04` is a hard bottleneck. Replicating `admin-api-mcp` does not increase throughput if `admin-api` is single-threaded or rate-limited.
-