

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Minutes (non-critical read-only data) |
| **Blast radius if down** | LiteLLM cannot inspect container state. AI assistants fail queries regarding running services, logs, or config on `tmtdockp01`. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Manual intervention if socket unavailable. |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Reads Docker daemon metadata via Model Context Protocol (MCP). Provides a secure abstraction layer for AI models to inspect container status, environment variables, and logs on the host `tmtdockp01`.

- **Primary purpose:** Read-only inspection of Docker objects (containers, images, networks).
- **Consumer pattern:** HTTP API exposed on port 3022 within `ai-mcp` network. LiteLLM acts as the sole gateway; no direct ingress from outside the homelab.
- **NOT used for:** Modifying containers, starting/stopping services, or executing commands (handled by `docker-mcp`).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local build (./docker-inspect)` (No external registry tag) |
| **Pinning policy** | None (local build context) |
| **Resource caps** | None defined |
| **Volumes** | `/var/run/docker.sock:/var/run/docker.sock:ro` (Critical)<br>`./shared:/app/shared:ro` (Read-only config) |
| **Networks** | `ai-mcp` (Docker bridge) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | `?` (Not defined in compose) |

### Configuration shape

- **Env vars:** Injected via `x-secrets_env` (ADMIN_API_URL, OP_CONNECT_TOKEN, MCP_API_KEY).
- **Runtime:** `PORT: "3022"`, `DOCKER_SOCKET_PATH: /var/run/docker.sock`.
- **Secrets fetch:** `SecretsProvider().get_secret(path)` called at container startup.

## Dependencies

### Hard (service cannot start or operate without these)
- **Docker Daemon:** Required for socket access (`/var/run/docker.sock`). If host daemon restarts, service reconnects automatically.
- **LiteLLM:** Network isolation gateway. Without it, the service is unreachable by consumers.
- **SecretsProvider:** Fails startup if 1Password Connect or Admin API is unreachable (blocks startup).

### Soft (degrade if these are down, but service still functional)
- **Admin API:** Used for configuration updates, not runtime operation.
- **1Password:** Fallback to env vars if Connect fails (per `x-secrets-env` logic).

### Reverse (services that depend on THIS service)
- **LiteLLM:** Routes AI requests. Breakage causes "container inspect" tools to fail silently or error.
- **AI Assistants:** End users querying system state.

## State & persistence

- **Database tables:** None.
- **Filesystem state:** None. Service is stateless.
- **In-memory state:** Session tokens cached briefly. Lost on restart.
- **External state:** None.
- **Logs:** `json-file` driver, `max-size: "10m"`, `max-file: "3"`. Retained on host.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% | > 50% sustained | Throttled by Docker daemon |
| Memory | < 100MB | > 500MB | OOMKilled (no limit set) |
| Disk I/O | Negligible | N/A | None |
| Network | Bursty (on query) | N/A | Bounded by host NIC |
| Request latency p50 | < 50ms | > 1s | Docker daemon load dependent |
| Request rate | < 10 req/min | > 100 req/min | N/A |

## Failure modes

- **Symptom:** `503 Service Unavailable` from LiteLLM.
  - **Root cause:** Secrets fetch timeout or Docker socket permission denied.
  - **Mitigation:** Restart container. Check `/var/run/docker.sock` permissions on host.
- **Symptom:** Container restarts loop.
  - **Root cause:** Network `ai-mcp` missing or Docker daemon down.
  - **Mitigation:** Verify host network stack.
- **Symptom:** Security alert on socket access.
  - **Root cause:** Compromised container reading host config.
  - **Mitigation:** Isolate network. Consider `tecnativa/docker-socket-proxy`.

## HA constraints (input to fleet-reliability design)

- **Replicable?** **No.**
  - Reason: Tied to specific host `/var/run/docker.sock`. Cannot run on multiple hosts simultaneously without remote daemon config (not present).
- **Coordination requirements:** None.
- **State sharing across replicas:** N/A (Single instance only).
- **Hardware bindings:**
  - **Socket:** Host kernel interface via `/var/run/docker.sock`.
  - **Host:** `tmtdockp01` (CMDB record).
- **Network constraints:**
  - **Port:** 3022 (Internal only, not exposed to host network).
  - **Network:** Must attach to `ai-mcp` bridge.
- **Cluster size constraints:** Fixed at 1.
- **Migration cost:** Low. Requires redeploy on new host + socket bind.
- **Security Constraint:** Docker socket bind mount is a high-risk surface. Read-only (`:ro`) mitigates some risk but allows full daemon introspection. Any compromise of this container grants visibility into all other containers on `tmtdockp01`.

## Operational history

### Recent incidents (last 90 days)
- `?` (No incidents recorded in CMDB)

### Recurring drift / chronic issues
- `?` (Service is new/phase 1 bulk backfill)

### Known sharp edges
- **Socket Security:** `docker-inspect` and `docker-mcp` both bind mount socket. If `docker-mcp` is compromised, `docker-inspect` adds no additional security barrier.
- **Secret Rotation:** If `MCP_API_KEY` rotates, container must restart to pick up new env var (no hot-reload mechanism defined).

## Open questions for Architect

- Should `docker-socket-proxy` be introduced to reduce socket attack surface?
- Is `tmtdockp01` the final host, or should this be abstracted to a node pool?
- How to handle `local build` image pinning in CI/CD for reproducibility?

## Reference

- **Compose:** `homelab-automation/stacks/mcp-servers/docker-compose.yml`
- **Logs:** `/var/lib/docker/containers/<id>/<id>-json.log`
- **Dashboards:** `?` (No Grafana panel defined)
- **Runbooks:** `?`
- **Upstream docs:** `?`
- **Related services:** `docker-mcp`, `LiteLLM`