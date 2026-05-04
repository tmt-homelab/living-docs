

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (service restarts on-failure). Data loss unacceptable. |
| **Blast radius if down** | `nemoclaw` agent service fails health checks → Ops Brain triage/automation stops. |
| **Recovery time today** | Auto-restart (Docker `on-failure`). Manual volume restore required for corruption. |
| **Owner** | `tmiller` (Human) / `phase-1.4-bulk-backfill` (Automation registration) |

## What this service actually does

Stores persistent state for the `nemoclaw` agent (Ops Brain). It maintains audit logs, playbook execution history, and Corvus operational governance data. The fleet uses it as a private backend for the `nemoclaw` container via a dedicated Docker network (`db-nemoclaw`).

It is **not** used for Prefect orchestration state (that lives in `prefect-postgres`), Home Assistant core state, or general application caching. It is strictly the persistence layer for the NemoClaw agent logic.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `postgres:16-alpine` |
| **Pinning policy** | Tag-floating (`16-alpine`). Minor version drift possible on rebuild. |
| **Resource caps** | `memory: 512M`, `cpus: '1.0'` |
| **Volumes** | `nemoclaw_postgres_data:/var/lib/postgresql/data` (Named volume) |
| **Networks** | `db-nemoclaw` (External, isolated from `homeauto` bridge) |
| **Secrets** | `${NEMOCLAW_DB_PASSWORD}` (Injected via 1Password Connect) |
| **Healthcheck** | `pg_isready -U nemoclaw -d nemoclaw` (Interval 10s, Retries 5) |

### Configuration shape

Standard PostgreSQL configuration. Connection string passed to `nemoclaw` agent via `DATABASE_URL` env var (`postgresql+asyncpg://...`). No custom `postgresql.conf` overrides in compose; relies on defaults. Secrets injected at container start via environment variables populated by the deploy workflow (1Password Connect).

## Dependencies

### Hard (service cannot start or operate without these)
- **None** (Database is self-contained).

### Soft (degrade if these are down, but service still functional)
- **1Password Connect** (if secret rotation required; service continues with existing credentials until restart).

### Reverse (services that depend on THIS service)
- **`nemoclaw`** — Connects via `db-nemoclaw` network. Fails health check immediately if DB unreachable. Blocks Ops Brain triage flows.

## State & persistence

- **Database tables**: `nemoclaw` schema (Audit logs, playbook state, Corvus records).
- **Filesystem state**: `/var/lib/postgresql/data` (Named volume `nemoclaw_postgres_data`).
- **In-memory state**: WAL buffers, query caches. Lost on restart (recovered from disk).
- **External state**: None (No S3 replication or external WAL archiving configured).
- **Backup status**: **⚠️ Unclear.** `restic-backup` service mounts `/mnt/docker-data` and `/mnt/docker`. Named volumes typically reside in `/var/lib/docker/volumes`. Verify if Docker root is symlinked to `/mnt/docker-data` to confirm inclusion in offsite B2 backups. RPO depends on Restic schedule (not visible in snippet).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (Idle) | > 50% sustained | Throttled by cgroup (1.0 cpus) |
| Memory | 200-400M | > 450M | OOM killed by cgroup |
| Disk I/O | Low (Write on audit log) | N/A | N/A |
| Network | < 1MB/s (Local bridge) | N/A | N/A |
| Request latency p50 | < 5ms | > 100ms | Connection queue build-up |
| Request rate | < 10 req/s | > 100 req/s | Latency spikes |

## Failure modes

- **Volume corruption**
    - **Symptom**: `nemoclaw` agent health check fails, Postgres logs show I/O errors.
    - **Root cause**: Disk failure or abrupt host power loss without WAL sync.
    - **Mitigation**: Restore `nemoclaw_postgres_data` from Restic backup (if coverage confirmed).
    - **Prevention**: Enable `fsync` (default), verify backup integrity weekly.

- **Password Rotation**
    - **Symptom**: `nemoclaw` agent logs "connection refused" or auth failure after deploy.
    - **Root cause**: `${NEMOCLAW_DB_PASSWORD}` env var updated in 1Password, but container not restarted.
    - **Mitigation**: `docker-compose up -d nemoclaw-postgres` to pick up new secret.
    - **Prevention**: Automate restart trigger on secret change in deploy pipeline.

- **Memory Pressure