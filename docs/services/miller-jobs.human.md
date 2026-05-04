

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (non-critical utility) |
| **Blast radius if down** | Job search dashboard offline; Slack job alerts stop; no impact on core infrastructure or other AI services |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual restore if DB corruption occurs |
| **Owner** | ? (Registered by `phase-1.4-bulk-backfill` in CMDB) |

## What this service actually does

Hosts a Next.js dashboard for internal job search aggregation. Polls Adzuna API for listings, processes matches via LiteLLM, and notifies users via Slack. Persists search history and user profiles in a local SQLite database.

Other services do not call this service. It acts as an outbound consumer only (Adzuna, Slack, Google Auth, LiteLLM). It is NOT a general-purpose job board API for external consumption; traffic is restricted to `jobs.themillertribe-int.org` via the proxy network.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/miller-jobs/docker-compose.yml` |
| **Image** | `miller-jobs:latest` (Local build, tag-floating) |
| **Pinning policy** | Tag-floating (`latest`); rebuilds on gitops sync |
| **Resource caps** | Memory: 512M, CPU: 1.0 vCPU |
| **Volumes** | `miller_jobs_data` (named, SQLite state), `/mnt/docker/stacks/miller-jobs/config` (bind, profiles.json) |
| **Networks** | `proxy` (ingress), `ai-services` (LiteLLM), `egress` (API access) |
| **Secrets** | Environment variables (ADZUNA, SLACK, GOOGLE, NEXTAUTH) injected via GitOps |
| **Healthcheck** | `wget --spider http://127.0.0.1:3000/api/health` (30s interval, 3 retries) |

### Configuration shape

Environment-heavy configuration. Required vars enforce startup failure if missing (`:?required`). External config file `/config/profiles.json` mounted read-write for user profiles. Database path hardcoded to `/data/miller-jobs.db`. No YAML config for application logic; logic is compiled into the image.

## Dependencies

### Hard (service cannot start or operate without these)
- `litellm` — AI matching engine (`http://litellm:4000/v1` on `ai-services` network). Service degrades to non-AI mode if unreachable (code dependent on logic).
- `adzuna_api` — External API. Failures result in no job data.
- `google_auth` — External OAuth. Blocks login if unavailable.
- `sqlite_file` — Local volume. Corrupt DB stops service.

### Soft (degrade if these are down, but service still functional)
- `slack_webhook` — Notifications fail silently if webhook URL invalid or Slack down.

### Reverse (services that depend on THIS service)
- None. CMDB records `dependencies: []`.

## State & persistence

- **Database:** `/data/miller-jobs.db` (SQLite). Single file. Contains user sessions, job history, search profiles.
- **Filesystem state:** `/config/profiles.json` (Bind mounted). Stores user preferences.
- **In-memory state:** Next.js session cache, job polling queues. Lost on restart.
- **External state:** None (Adzuna/Slack store data externally).
- **Backup:** Named volume `miller_jobs_data`. No explicit backup job defined in compose. RPO/RTO depends on fleet-level volume backup strategy (?).
- **Replication:** Not supported. SQLite file locking prevents concurrent writes across replicas without shared storage coordination.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 10% (polling intervals) | > 80% sustained | Throttled by 1.0 limit |
| Memory | 100-200MB | > 480MB | OOM Kill (512M limit) |
| Disk I/O | Low (periodic writes) | N/A | SQLite lock contention |
| Network | Low (polling) | N/A | Egress blocked by firewall |
| GPU | N/A | N/A | N/A |
| Request latency p50 | < 200ms | > 2s | Timeout on healthcheck |
| Request rate | Low (user traffic) | N/A | N/A |

## Failure modes

- **SQLite Lock Error**: Symptom: 500 errors on writes. Root cause: Concurrent access or WAL mode disabled. Mitigation: Restart container. Prevention: Ensure single replica.
- **API Key Expiry**: Symptom: 401 errors in logs. Root cause: Adzuna/Slack token rotation. Mitigation: Update env vars via GitOps. Prevention: ?
- **LiteLLM Unreachable**: Symptom: AI matching fails. Root cause: Network partition or LiteLLM down. Mitigation: Check `ai-services` network. Prevention: ?
- **OOM Kill**: Symptom: Container restarts loop. Root cause: Memory leak or config bloat. Mitigation: Increase limit (temp), check logs. Prevention: Profile memory usage.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. SQLite database file is not designed for multi-master or active-active replication without shared storage (NFS/iSCSI) which introduces latency and locking complexity.
- **Coordination requirements** None. Standalone process.
- **State sharing across replicas** Impossible with current architecture. Requires DB dump/restore or shared block storage (not configured).
- **Hardware bindings** None. Standard x86_64 container.
- **Network constraints** Must reach `litellm:4000` on `ai-services` network. Must egress to Adzuna/Slack/Google. Port 3000 exposed only internally (via `proxy` network).
- **Cluster size constraints** Fixed at 1. Increasing to >1 requires architectural change (migrate from SQLite to Postgres/MySQL).