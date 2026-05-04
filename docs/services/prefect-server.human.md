

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "Minutes" (orchestration queues backlog; workers retry connection) |
| **Blast radius if down** | All automation flows stop scheduling. `prefect-worker`/`prefect-worker-blog` lose API connection. `admin-api` metrics collection breaks. Home Assistant automation via Prefect halts. |
| **Recovery time today** | Auto-restart (`on-failure`); manual DB intervention if corruption occurs. |
| **Owner** | `tmiller` (CMDB registered by `claude-code`) |

## What this service actually does

Prefect Server is the orchestration control plane. It stores flow run state, schedules deployments, and exposes the UI/API. It does **not** execute flows; workers (`prefect-worker`, `prefect-worker-blog`) pull work from this API.

The fleet uses it to trigger Home Assistant automations, GitOps syncs, and blog drafts via registered flows. The `admin-api` consumes metrics from it. When broken, no new tasks start, and existing long-running flows may orphan if the Foreman service cannot detect heartbeats.

It is NOT a task executor. It is NOT a message queue (though it queues runs in DB). It is NOT a persistent storage backend (Postgres handles that).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `prefecthq/prefect:3-latest` |
| **Pinning policy** | Tag-floating (`3-latest`) — **RISK**: Version drift on rebuild. |
| **Resource caps** | None defined in Compose (unconstrained). |
| **Volumes** | `prefect_data:/root/.prefect` (config only). DB state in `prefect_postgres_data` (via `prefect-postgres` service). |
| **Networks** | `infra-services` (Caddy/API), `automation` (internal), `db-prefect` (DB only). |
| **Secrets** | `1Password Connect` (injected via `${POSTGRES_PASSWORD}`, `${HA_TOKEN}`, etc.). |
| **Healthcheck** | `http://127.0.0.1:4200/api/health` (30s interval, 3 retries). |

### Configuration shape

Configuration is driven by environment variables injected at deploy time. Key surfaces:
- `PREFECT_API_DATABASE_CONNECTION_URL`: Hardcoded to internal `prefect-postgres` DNS.
- `PREFECT_SERVER_API_HOST`: Bound to `0.0.0.0`.
- Service loops (Foreman, Late Runs, Cancellation Cleanup) tuned via env vars (e.g., `PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS=30`).
- CSRF protection disabled (`PREFECT_SERVER_CSRF_PROTECTION_ENABLED=false`) for internal API trust.

## Dependencies

### Hard (service cannot start or operate without these)
- `prefect-postgres` — Stores all flow run state. If down, Server crashes or fails healthchecks. Connection string points to internal DNS `prefect-postgres:5432`.

### Soft (degrade if these are down, but service still functional)
- `admin-api` — Metrics ingestion breaks, but orchestration continues.
- `prefect-worker` — Flows queue but don't execute.

### Reverse (services that depend on THIS service)
- `prefect-worker` — Polls for work. Breaks run execution.
- `prefect-worker-blog` — Polls `blog-pipeline-pool`. Breaks blog generation.
- `admin-api` — Scrapes `/prefect/metrics`. Breaks dashboard visibility.

## State & persistence

- **Database**: `prefect-postgres` (Postgres 16 Alpine). Tables: `flow_run`, `deployment`, `block_document`. Backup via `restic-backup` targeting `/mnt/docker-data` (includes volume `dockp04-automation_prefect_postgres_data`). RPO: ~1 hour (restic schedule).
- **Filesystem**: `/root/.prefect` (mounted `prefect_data`). Contains `server.yml` and credentials cache. Low growth.
- **In-memory**: Run state cache. Lost on restart (recovered from DB).
- **External state**: None (all state internal to stack).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 1-5% | >50% sustained | Flow scheduling spikes; workers stall. |
| Memory | 200-400MB | >1GB | OOM killed if unconstrained. |
| Disk I/O | Low (DB writes) | High (log churn) | Log volume grows if flow runs >10k/day. |
| Network | 10KB/s | >1MB/s | API lag increases under load. |
| Request latency p50 / p95 / p99 | 20ms / 100ms / 500ms | p99 > 2s | Queue backlog visible in UI. |
| Request rate | 5 req/s | >100 req/s | Workers overwhelm API. |

## Failure modes

- **Zombie Runs**: Worker dies mid-flow, Server marks "Running" forever. **Mitigation**: Foreman service loop (`PREFECT_API_SERVICES_FOREMAN_LOOP_SECONDS=30`) detects missing heartbeats. **Prevention**: Worker `PREFECT_RUNNER_HEARTBEAT_FREQUENCY=30` configured.
- **DB Connection Loss**: Server crashes loop. **Mitigation**: Docker `restart: on-failure`. **Prevention**: Postgres healthcheck dependency.
- **Version Drift**: `3-latest` tag updates unexpectedly. **Mitigation**: Manual pin. **Prevention**: Switch to digest pinning.
- **CMDB Drift**: CMDB lists host `tmtdockp01`, Compose lists `tmtdockp04`. **Mitigation**: Verify inventory. **Prevention**: Sync CMDB with Compose host.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (not currently configured). Prefect Server 3 supports high availability but requires shared Postgres and careful configuration. Current stack uses single `container_name: prefect-server`.
- **Coordination requirements**: None (single instance). If replicating, requires shared Postgres and consistent `PREFECT_SERVER_API_URL`.
- **State sharing across replicas**: **Shared DB** (`prefect-postgres`). File state (`/root/.prefect`) should not be shared (conflict risk).
- **Hardware bindings**: None.
- **Network constraints**: Port `4200` must be unique per instance. API URL must be resolvable by workers (`prefect-server` DNS name).
- **Cluster size constraints**: Single instance currently. Moving to N replicas requires Postgres HA (e.g., Patroni) and load balancer.
- **Migration cost**: High. Requires externalizing Postgres to a managed service or cluster. Current DB is ephemeral to the stack (volume backed). Data migration script needed if moving to external DB.
- **Restart impact**: Rolling restarts possible if Postgres is stable. Zero-downtime deployment requires external load balancer + health checks.

## Operational history

### Recent incidents (last 90 days)
- `2026-05-03` — Zombie runs detected. Root cause: Worker died without cleanup. Resolution: Enabled Foreman/Cancellation-Cleanup loops in env vars.
- `2026-04-06` — CMDB record created by `claude-code`. Host mismatch recorded.

### Recurring drift / chronic issues
- **Host mismatch**: CMDB says `tmtdock