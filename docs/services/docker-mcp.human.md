

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) but `3` (single-instance hardware bound) |
| **Tolerable outage** | 30 minutes (AI tool degradation, not system down) |
| **Blast radius if down** | LiteLLM AI assistants lose container introspection/management capabilities; no impact on running containers |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual intervention if socket perms change |
| **Owner** | ? (registered_by: `phase-1.4-bulk-backfill`) |

## What this service actually does

`docker-mcp` exposes the Docker Engine API to AI agents via the Model Context Protocol (MCP). It acts as a bridge between LLMs and the host's container runtime.

Primary purpose: Allow AI to inspect containers, view logs, and execute limited operations (restart, stop) based on `are_you_sure=True` confirmation logic.

How it's used:
- **Consumer:** LiteLLM (via `ai-mcp` network) sends MCP JSON-RPC requests.
- **Access:** Connects directly to host Docker Daemon via bind-mounted `/var/run/docker.sock`.

What it is NOT:
- Not a container orchestrator (Portainer handles UI/orchestration).
- Not a generic log aggregator (Netdata/Splunk handle metrics/logs).
- Not read-only: `DOCKER_READ_ONLY: "false"` allows write operations (stop/start/exec).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context: `./docker`) |
| **Pinning policy** | None (rebuilds on `docker compose up --build`) |
| **Resource caps** | None defined in compose |
| **Volumes** | `/var/run/docker.sock:/var/run/docker.sock:ro` (Critical), `./shared:/app/shared:ro` |
| **Networks** | `ai-mcp` (External, isolated), `tmtdockp01` host routing |
| **Secrets** | 1Password: `services/docker-mcp/mcp_api_key`, `services/docker-mcp/docker_socket_path` |
| **Healthcheck** | None defined (relies on `restart: unless-stopped`) |

### Configuration shape

- **Env Vars:** `DOCKER_SOCKET_PATH`, `DOCKER_READ_ONLY`, `DOCKER_ENABLE_EXEC`.
- **Secrets:** Fetched at startup via `SecretsProvider` (Admin API -> 1Password fallback).
- **Auth:** Bearer token (`MCP_API_KEY`) validated per request.
- **Routing:** `ADMIN_API_URL` targets `http://<DOCKP04_IP>:8000` (cross-host via routing).

## Dependencies

### Hard (service cannot start or operate without these)
- **Docker Daemon** (Host `tmtdockp01`) — Socket mount required for API access.
- **SecretsProvider** — Startup blocks if Admin API/1Password unreachable.
- **LiteLLM** — Sole ingress gateway (no direct external routing).

### Soft (degrade if these are down, but service still functional)
- **Admin API** (`dockp04`) — Required for secret refresh, not initial startup if cached.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI tool calls to this endpoint.
- **AI Agents** — Directly impacted if this service is down.

## State & persistence

- **Database tables / schemas:** None.
- **Filesystem state:** None. Reads only from host socket and shared read-only volume.
- **In-memory state:** Connection state to Docker daemon (lost on restart).
- **External state:** None.
- **Backup:** Not applicable (stateless), but socket permissions must be version-controlled in host config.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | Low, spikes on `docker exec` |
| Memory | ? | ? | Low, bounded by container overhead |
| Disk I/O | ? | ? | None (read-only mounts) |
| Network | ? | ? | Minimal (JSON-RPC) |
| GPU | N/A | N/A | N/A |
| Request latency | ? | > 5s | Depends on Docker daemon load |
| Request rate | ? | > 100 req/min | Rate limited by MCP protocol |

## Failure modes

- **Symptom:** `503` from LiteLLM; AI reports "Tool unavailable".
- **Root cause:** Docker daemon socket permissions changed (e.g., host update).
- **Mitigation:** Verify `root:docker` group on host; restart container.

- **Symptom:** Container crashes on startup.
- **Root cause:** SecretsProvider timeout (Admin API unreachable).
- **Mitigation:** Check `ADMIN_API_URL` connectivity from `tmtdockp01`.

- **Symptom:** Security alert (privilege escalation risk).
- **Root cause:** `DOCKER_READ_ONLY: "false"` allows arbitrary exec.
- **Mitigation:** Enforce `are_you_sure=True` in client logic; consider `docker-socket-proxy`.

## HA constraints (input to fleet-reliability design)

- **Replicable?** **No.** Single-instance bound to host socket.
- **Coordination requirements:** None (no leader election needed).
- **State sharing across replicas:** Not applicable. Cannot run multiple instances on same host socket without conflict.
- **Hardware bindings:** **Critical.** Requires `/var/run/docker.sock` access on specific host (`tmtdockp01`). Cannot be moved to `dockp02` without changing host config.
- **Network constraints:** Restricted to `ai-mcp` network. Cannot expose port directly to internet.
- **Cluster size constraints:** Max 1 instance per host.
