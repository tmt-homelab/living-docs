

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (Prefect control plane halts; flows stall) |
| **Blast radius if down** | `prefect-server` becomes unreachable; `prefect-worker` loses run state; `admin-api` metrics broken |
| **Recovery time today** | Auto-restart (`on-failure`) + manual volume restore if corrupt |
| **Owner** | `?` (CMDB `registered_by`: `phase-1.4-bulk-backfill`; inferred `tmiller`) |

## What this service actually does

Stores orchestration state for the Prefect automation stack. It is the source of truth for flow runs, deployments, task caching, and worker heartbeats. The fleet uses it exclusively via the `prefect-server` container over the `db-prefect` network. When it's broken, all automation visibility vanishes (runs show as pending/unknown) and workers cannot report completion.

It is NOT used for NemoClaw data (separate `nemoclaw-postgres` instance). It is NOT used for blog draft storage (mounted bind volume on workers). It is NOT exposed to the public internet or the `homeauto` network.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `postgres:16-alpine` |
| **Pinning policy** | Tag-floating (`:16-alpine`). Minor version drift possible on rebuild. |
| **Resource caps** | None defined (inherits host defaults) |
| **Volumes** | `dockp04-automation_prefect_postgres_data` → `/var/lib/postgresql/data` (Named volume, state) |
| **Networks** | `db-prefect` (External bridge, isolated from `homeauto`) |
| **Secrets** | `POSTGRES_PASSWORD` (Env var, sourced from 1Password Connect context) |
| **Healthcheck** | `pg_isready -U prefect -d prefect` (10s interval, 5 retries) |

### Configuration shape

Minimal configuration surface. Relies entirely on environment variables for initialization (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`). No `postgresql.conf` or `pg_hba.conf` overrides; uses default Alpine Postgres settings. Connection string for `prefect-server` is hardcoded in env var `PREFECT_API_DATABASE_CONNECTION_URL`.

## Dependencies

### Hard (service cannot start or operate without these)
- **None** (Self-contained database engine; assumes local storage and network stack).

### Soft (degrade if these are down, but service still functional)
- **None** (Database does not depend on external APIs).

### Reverse (services that depend on THIS service)
- **`prefect-server`**: Critical dependency. Starts only after `prefect-postgres` is healthy (`condition: service_healthy`). All API traffic routes through this service.
- **`prefect-worker`**: Indirect dependency. Workers poll `prefect-server` for state. If DB is down, workers cannot confirm run status.
- **`admin-api`**: Indirect dependency. Queries `prefect-server` for metrics (`/prefect/metrics`); metrics break if DB is down.

## State & persistence

State resides exclusively in the Docker named volume `dockp04-automation_prefect_postgres_data`.

- **Database tables**: Prefect schema (flows, runs, deployments, logs). Growth rate: Low (homelab scale), but unbounded if retention policies are not set in Prefect config.
- **Filesystem state**: `/var/lib/postgresql/data`. Contains WAL files and data files.
- **In-memory state**: Query cache (lost on restart).
- **External state**: None.
- **Backup status**: **`?`** (Restic config at `restic-backup` mounts `/mnt/docker`, but named volumes typically reside in `/var/lib/docker/volumes`. Explicit bind mount for this volume is not visible in `restic-backup` definition. Risk of data loss on host wipe is high).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 80% | Throttling on workers |
| Memory | ~200MB | > 90% of host