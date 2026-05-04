

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (Blog is non-critical) |
| **Blast radius if down** | `blog-ghost` read/write fails; Admin panel 502/504; No new posts/comments |
| **Recovery time today** | Auto-restart (`on-failure`); Data recovery depends on external backup |
| **Owner** | `tmttodd` (via `github.com/tmttodd/homelab-gitops`) |

## What this service actually does

Stores Ghost CMS relational data (posts, users, settings, integrations). The fleet uses it exclusively for `blog-ghost` via TCP/3306. It is not used for system metrics, other applications, or general homelab storage.

When down, the CMS cannot render content (read path broken) and editors cannot save drafts (write path broken). It is the single source of truth for the `overlabbed.com` content store.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/blog/docker-compose.yml` |
| **Image** | `mysql:8.0` |
| **Pinning policy** | Tag-floating (`8.0`); minor version drift possible on rebuild |
| **Resource caps** | `?` (Not defined in compose) |
| **Volumes** | `blog_mysql_data` (named, stateful) at `/var/lib/mysql` |
| **Networks** | `blog-internal` (isolated bridge) |
| **Secrets** | `${GHOST_DB_PASSWORD}`, `${GHOST_DB_ROOT_PASSWORD}` (Env vars, source unknown) |
| **Healthcheck** | `mysqladmin ping -h 127.0.0.1` (10s interval, 5 retries) |

### Configuration shape

Standard MySQL 8.0 defaults. Database, user, and password initialized via ENV vars at first run. No custom `my.cnf` mounted. Environment variables sourced from runtime context (likely `.env` or secret injection).

## Dependencies

### Hard (service cannot start or operate without these)
- `None` (Self-contained; does not depend on other services in compose)

### Soft (degrade if these are down, but service still functional)
- `None`

### Reverse (services that depend on THIS service)
- `blog-ghost` — Connects via `blog-mysql:3306`. Fails immediately on DB connection loss.
- `cloudflared-blog` — Depends on `ghost` health, indirectly dependent on DB.

## State & persistence

- **Database tables**: InnoDB engine. `ghost` schema. Growth rate: Low (text-heavy).
- **Filesystem state**: `/var/lib/mysql` contains raw data files, logs, and socket. Stored in `blog_mysql_data` volume.
- **In-memory state**: Query cache, buffer pool. Lost on restart (rehydrated from disk).
- **External state**: None (no S3/external DB configured).
- **Backup Strategy**: `?` (No backup job visible in compose or CMDB).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% idle | > 80% sustained | Throttling if caps exist |
| Memory | ? | ? | OOM kill if host pressure |
| Disk I/O | Low (random read/write) | ? | Write latency spikes on full disk |
| Network | Internal only | ? | Connection refused if saturated |
| GPU | N/A | N/A | N/A |
| Request latency p50 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Disk Full**: Logs or data fill host volume.
  - *Symptom*: DB hangs, `ghost` timeouts.
  - *Mitigation*: Clear logs, expand volume.
  - *Prevention*: Host monitoring on `/mnt/docker`.
- **Version Mismatch**: `mysql:8.0` tag updates minor version.
  - *Symptom*: Startup failure, data format incompatibility.
  - *Mitigation*: Restore from backup.
  - *Prevention*: Pin digest.
- **Env Var Loss**: Secrets missing at restart.
  - *Symptom*: Container exits immediately (missing password).
  - *Mitigation*: Restore env config.
  - *Prevention*: Use secret manager, not plaintext `.env`.

## HA constraints (input to fleet-reliability design)

- **Replicable**: No. State is local to `blog_mysql_data` volume.
- **Coordination requirements**: None. Single master model.
- **State sharing across replicas**: None. Cannot run multiple instances reading same volume concurrently (data corruption risk).
- **Hardware bindings**: None. Runs on standard x86_64.
- **Network constraints**: Port 3306 bound to `blog-internal` network. No external exposure.
- **Cluster size constraints**: 1 instance max in current design.
- **Migration cost**: High. Moving to HA requires:
  1. Schema lock during migration.
  2. Logical dump/restore or setting up replication (binlogs) not currently configured.
  3. DNS failover logic (Cloudflare Tunnel only points to one ghost instance).
- **Failure Domain**: Host `tmtdockp04`. If host dies, service is offline until rescheduled.
- **Data Durability**: Relies on Docker volume driver persistence. No native replication or snapshotting configured.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (`baseline_behavior` empty).

### Recurring drift / chronic issues
- Image tag `8.0` may pull new minor version unexpectedly.
- Secrets stored as ENV vars rather than mounted secret files.

### Known sharp edges
- **Root Password**: `MYSQL_ROOT_PASSWORD` exposed in ENV. Should be masked in logs.
- **Volume Lock**: `blog_mysql_data` cannot be mounted to another node without network filesystem (NFS/Ceph) which is not present.

## Open questions for Architect

- ? What is the backup strategy for `blog_mysql_data`?
- ? Are resource limits (CPU/RAM) enforced on `tmtdockp04` to prevent noisy neighbor issues?
- ? Should MySQL be upgraded to 8.4 or pinned to a specific digest?
- ? Is there a plan to migrate to a centralized DB cluster for homelab services?

## Reference

- **Compose**: `homelab-media/stacks/blog/docker-compose.yml`
- **Logs**: Docker `json-file` (`max-size: 50m`, `max-file: 3`)
- **Dashboards**: ?
- **Runbooks**: ?
- **Upstream docs**: `https://dev.mysql.com/doc/refman/8.0/en/`
- **Related services**: `blog-ghost`, `cloudflared-blog`