

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `2` (replicable stateful) — Logic is stateless, but `docker.sock` binding creates host affinity. |
| **Tolerable outage** | 15 minutes (Flow runs pause/retry via Prefect Server Foreman). |
| **Blast radius if down** | Infrastructure automation flows (DNS, GitHub sync, HA state) stop queuing. Existing runs hang until Foreman marks Crashed (30s heartbeat loop). |
| **Recovery time today** | Auto-restart (`on-failure`), but flow rescheduling requires manual intervention if pool capacity is exhausted. |
| **Owner** | `claude-code` (CMDB `registered_by`) |

## What this service actually does

Executes Prefect flows registered to the `default-pool`. It acts as the compute engine for homelab automation, translating flow definitions into actions against external systems (PowerDNS, GitHub, Home Assistant, LiteLLM). It polls the `prefect-server` API for work, executes the Python code locally, and reports status back.

Other fleet services use it indirectly via the Prefect API. `nemoclaw` may trigger flows via the API, and `admin-api` likely triggers infrastructure sync flows. It is **NOT** the orchestration brain (that is `prefect-server`) and **NOT** the data store (`prefect-postgres`).

It is distinct from `prefect-worker-blog`: the main worker has root access via `docker.sock` for container management within flows, whereas the blog worker is hardened (non-root, read-only, no socket).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `prefect-worker:latest` (Local build from `Dockerfile.worker`) |
| **Pinning policy** | Tag-floating (`latest`). **Risk:** Local builds without digest pinning may drift from `prefect-server` version. |
| **Resource caps** | None defined on `prefect-worker` (unlike `prefect-worker-blog` which has 1g/1.0). |
| **Volumes** | `/var/run/docker.sock` (State: Privileged Access), `/mnt/docker/blog-drafts` (State: Draft storage) |
| **Networks** | `automation`, `infra-services` |
| **Secrets** | 1Password Connect items: `POSTGRES_PASSWORD`, `HA_TOKEN`, `ADMIN_API_TOKEN`, `DNS_API_KEY`, `GITHUB_PAT`, `LITELLM_MASTER_KEY` |
| **Healthcheck** | `CMD-SHELL`: Checks `/proc/1/cmdline` contains 'prefect'. Interval: 30s. |

### Configuration shape

Configuration is environment-driven. Key variables injected at deploy time via 1Password Connect. The worker connects to `prefect-server` via `PREFECT_API_URL` (internal DNS `prefect-server:4200`). External dependencies (HA, DNS, GitHub) are resolved via hard-coded IPs (`192.168.20.222`, `192.168.20.250`, etc.) to avoid Docker DNS bridge dependency issues during restarts.

## Dependencies

### Hard (service cannot start or operate without these)
- `prefect-server` — API endpoint for task registration and heartbeat. Without this, worker cannot poll for work or report status.
- `prefect-postgres` — Underlying DB for `prefect-server`. Worker fails if Server is unreachable due to DB issues.
- Docker Daemon — Required for `docker.sock` mount. If host Docker crashes, worker is useless.

### Soft (degrade if these are down, but service still functional)
- `admin-api` — Used for auxiliary API calls within flows.
- `powerdns` — Flow target. Flows fail if DNS is down.
- `homeassistant` — Flow target (ipvlan `192.168.20.222`).
- `litellm` — AI classification endpoint.

### Reverse (services that depend on THIS service)
- `prefect-server` — Relies on worker heartbeats to manage flow state. If worker dies without shutdown signal, Foreman marks runs Crashed.
- `nemoclaw` — Likely consumes flow results or triggers flows via API.

## State & persistence

- **Database tables / schemas:** None locally. All state (flow runs, task results) lives in `prefect-postgres`.
- **Filesystem state:** `~/.prefect` (config, auth tokens). Persisted in container layer or ephemeral volume. `/mnt/docker/blog-drafts` is mounted for flow artifact access.
- **In-memory state:** Flow execution context. Lost on restart.
- **External state:** `docker.sock` provides access to host Docker state. This is the primary "state" dependency — the worker assumes it can spawn containers