

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (Recorder stops writing; automations continue if cached) |
| **Blast radius if down** | `homeassistant` → Recorder service fails. History UI breaks. Long-term stats unavailable. |
| **Recovery time today** | Auto-restart (`unless-stopped`); Data restoration requires manual snapshot restore |
| **Owner** | `tmt_todd` (GitOps repo owner) |

## What this service actually does

Stores long-term telemetry and event history for the Home Assistant instance. The fleet uses it via direct TCP connection on the `db-ha` network. When it's broken, the Home Assistant frontend loses historical graphs, and the recorder component errors out. It is NOT used for device configuration, MQTT state, or Zigbee pairing data (those live in `homeassistant` config volumes and MQTT broker).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `postgres:16-alpine` |
| **Pinning policy** | Tag-floating (`16-alpine`); minor version drift risk |
| **Resource caps** | `unknown` (None defined in compose) |
| **Volumes** | `/mnt/docker/homeassistant-postgres/data:/var/lib/postgresql/data` (State) |
| **Networks** | `db-ha` (External bridge) |
| **Secrets** | `${HA_POSTGRES_PASSWORD}` (Env var substitution) |
| **Healthcheck** | `pg_isready -U homeassistant` (10s interval, 5 retries) |

### Configuration shape

Standard Postgres initialization via environment variables (`POSTGRES_USER`, `POSTGRES_DB`). Data directory fixed at `/var/lib/postgresql/data/pgdata`. No custom `postgresql.conf` or `pg_hba.conf` mounted; relies on defaults.

## Dependencies

### Hard (service cannot start or operate without these)
- None (OS network/storage only)

### Soft (degrade if these are down, but service still functional)
- None

### Reverse (services that depend on THIS service)
- `homeassistant` — Writes recorder events. If DB down, HA logs "Recorder failed to initialize". UI history tab returns 500s.

## State & persistence

- **Database tables / schemas:** `homeassistant` DB. Tables grow linearly with event volume (events, states, statistics).
- **Filesystem state:** `/mnt/docker/homeassistant-postgres/data`. Contains PostgreSQL `base`, `global`, `pg_wal`.
- **Growth rate:** `?` (Depends on entity count and `recorder` purge settings).
- **In-memory state:** Shared buffers, WAL cache. Lost on restart.
- **External state (S3, etc.):** `?` (No offsite backup configured in compose).
- **Backup strategy:** `?` (Not defined in GitOps manifest).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (Idle writes) | > 80% sustained | DB locks on write contention |
| Memory | 512MB - 2GB | OOM killer | Connection queue fills |
| Disk I/O | Write-heavy (Append) | Latency > 50ms | WAL spill to disk |
| Network | Local bridge only | N/A | N/A |
| Request latency p50 / p95 / p99 | 5ms / 10ms / 50ms | > 1s | Connection timeouts |
| Request rate | Bursty (Event spikes) | N/A | N/A |

## Failure modes

- **Symptom:** `homeassistant` logs "Database is locked" or "Recorder failed".
- **Root cause:** Disk full on `/mnt/docker`.
- **Mitigation:** Clear old snapshots/logs on host; restart service.
- **Prevention:** Add disk usage alert on `/mnt/docker`.

- **Symptom:** Healthcheck fails but container running.
- **Root cause:** `pg_isready` timeout; DB accepting connections but slow.
- **Mitigation:** Check WAL volume; kill long-running queries.
- **Prevention:** Tune `checkpoint_timeout`; enable vacuuming.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (Requires primary-replica streaming setup not present).
- **Coordination requirements:** None (Standalone instance).
- **State sharing across replicas:** Impossible (Postgres data dir cannot be mounted read-write across nodes without shared storage).
- **Hardware bindings:** None.
- **Network constraints:** Must reach `db-ha` network. Port 5432 exposed only to container network.
- **Cluster size constraints:** Single instance only.
- **Migration cost:** High. Moving to HA requires:
    1. Dump/restore or logical replication setup.
    2. `homeassistant` config update (connection string).
    3. Downtime during cutover.
- **Failure domain:** Single host (`tmtdockp04`). If host dies, service dies.
- **Data durability:** Depends on underlying host disk (RAID/ZFS status unknown).

## Operational history

### Recent incidents (last 90 days)
- `?` (No incident data available in CMDB)

### Recurring drift / chronic issues
- Image tag floating (`16-alpine`) may pull new minor versions on `docker-compose pull`.
- Volume path `/mnt/docker` is host-specific; not portable without rsync.

### Known sharp edges
- Do not change `POSTGRES_DB` name after init; breaks `homeassistant` connection.
- Do not run `VACUUM FULL` during peak hours; locks tables.

## Open questions for Architect

- What is the RPO for this volume? Is `/mnt/docker` backed up by host-level tools (Proxmox/TimeShift)?
- Should we pin the image digest instead of tag `16-alpine`?
- Is there a plan to migrate to a managed DB or Patroni cluster for HA?
- What is the retention policy for the DB? Is there an automated `purge` job?

## Reference

- Compose: `homelab-homeauto/stacks/homeauto/docker-compose.yml`
- Logs: `/var/lib/docker/containers/*/homeassistant-postgres-json.log` (Docker daemon)
- Dashboards: `?` (No Grafana integration defined)
- Runbooks: `?`
- Upstream docs: https://www.postgresql.org/docs/16/index.html
- Related services: `homeassistant` (Consumer)