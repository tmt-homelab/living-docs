

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes. Data loss acceptable only if explicit backup restoration is initiated. |
| **Blast radius if down** | All consumers on `infra-db` network attempting TCP `5432` will fail. Specific consumer list unrecorded in CMDB. |
| **Recovery time today** | `restart: on-failure` triggers Docker restart. State recovery depends on ZFS dataset integrity; manual intervention required if WAL/data corruption occurs. |
| **Owner** | `?` (CMDB registered_by: `claude-code`; no human owner assigned) |

## What this service actually does

`postgres` stores relational state for fleet services. It is accessed exclusively via TCP `5432` over the `infra-db` Docker network. The fleet uses it as the primary RDBMS backend for structured data, authentication stores, or application state. When it is broken, dependent services cannot complete transactions, fail to authenticate, or refuse to start if they require a reachable database on boot.

This service is **not** used for caching (handled by `redis:8-alpine` in the same stack), **not** used for blob/media storage (handled by ZFS datasets), and **not** exposed to the public internet despite the host port mapping.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/dockp04-core/docker-compose.yml` |
| **Image** | `postgres:16-alpine` |
| **Pinning policy** | Tag-floating. No digest. Acceptable for minor Alpine/Patch updates but introduces uncontrolled schema/WAL format drift risk during `docker pull`. |
| **Resource caps** | None defined. Subject to host cgroup limits. |
| **Volumes** | Bind mount: `/mnt/media/infra/postgres` → `/var/lib/postgresql/data` (state). Host path is a ZFS dataset configured with `recordsize=8K`. |
| **Networks** | `infra-db` (external bridge). Host port `5432:5432` bound to `0.0.0.0` by default. |
| **Secrets** | `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}` via `.env` or 1Password Connect. |
| **Healthcheck** | `pg_isready -U ${POSTGRES_USER:-postgres}`. Interval `10s`, timeout `5s`, retries `5`, start_period `30s`. |

### Configuration shape
Minimal, environment-driven configuration. The `POSTGRES_DB` is hardcoded to `postgres`. No custom `postgresql.conf` or `pg_hba.conf` bind mounts are present. All tuning relies on upstream defaults and runtime env vars. Configuration is not version-controlled or explicitly declared in the compose file.

## Dependencies

### Hard (service cannot start or operate without these)
- **ZFS Dataset (`/mnt/media/infra/postgres`)** — backs the data directory. If unmounted or degraded, PG will fail to start or refuse writes.
- **Docker Runtime & `infra-db` Network** — required for container execution and service discovery.

### Soft (degrade if these are down, but service still functional)
- None recorded.

### Reverse (services that depend on THIS service)
- `?` — CMDB dependencies array is empty. Likely internal dashboards, auth providers, or app backends using `infra-db`. Needs fleet-wide service mapping audit.

## State & persistence

- **Filesystem state:** `/var/lib/postgresql/data` contains base tablespaces, WAL segments, pg_wal, and pg_logical. Mapped to `/mnt/media/infra/postgres` (ZFS). The `recordsize=8K` ZFS property aligns with PG's default block size and reduces write amplification.
- **Backup strategy:** None defined in compose or CMDB. RPO/RTO currently `?`. Likely relies on ad-hoc ZFS snapshots or manual `pg_dump` (unverified).
- **State sharing:** Not shareable across replicas. PostgreSQL requires exclusive access to the data directory. Concurrent mounts cause immediate corruption.
- **In-memory state:** Shared buffers, WAL buffers, lock table, and temporary statistics are lost on restart. Relies on WAL replay for crash recovery.

## Failure modes

- **ZFS dataset exhaustion/corruption**
  - *Symptom:* `pg_isready` fails repeatedly, container enters restart loop, `journalctl`/Docker logs show I/O errors.
  - *Root cause:* Host disk full, ZFS pool degraded, or checksum mismatch.
  - *Mitigation:* Restore from ZFS snapshot, clear pool, or attach replacement disk.
  - *Prevention:* Monitor pool health, enforce dataset quotas, implement continuous WAL archiving.

- **Tag drift / unattended major update**
  - *Symptom:* Container pulls `postgres:16-alpine` update, crashes on start due to `initdb` conflict or changed default settings.
  - *Root cause:* Floating tag pulls new minor/major version without migration script.
  - *Mitigation:* Pin image, rollback container, or run `pg_upgrade` manually.
  - *Prevention:* Digest pinning or automated update gating with pre-flight migration checks.

- **Host port exposure (`5432:5432`)**
  - *Symptom:* Unintended connections from outside `infra-db` network; firewall noise.
  - *Root cause:* Default `0.0.0.0:5432` bind in compose.
  - *Mitigation:* Remove port mapping; route via internal `infra-db` network or reverse proxy.
  - *Prevention:* Restrict bind to `127.0.0.1:5432` or remove entirely.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. PostgreSQL is not shippable or multi-primary by default. Requires explicit