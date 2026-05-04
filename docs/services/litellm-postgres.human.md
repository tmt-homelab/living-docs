

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (LiteLLM restarts; config loss if volume corruption) |
| **Blast radius if down** | `litellm` fails health check → All AI chat/embed/rerank routing stops (OpenWebUI, vLLM clients) |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual restore if volume corrupt |
| **Owner** | ? (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

PostgreSQL backend for LiteLLM proxy. Stores model routing configuration, API keys, user permissions, and usage logs. The `litellm` service connects to this DB to validate requests and persist proxy state.

- **Primary purpose**: Persistent storage for LiteLLM configuration and metadata.
- **Consumer pattern**: `litellm` connects via TCP (port 5432) using `DATABASE_URL` env var.
- **Not used for**: User chat history (OpenWebUI), vector embeddings (Milvus), or model weights (vLLM local FS).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `postgres:16-alpine` (tag-floating) |
| **Pinning policy** | Tag-floating (minor version 16); no digest pinning in compose |
| **Resource caps** | None defined (default Docker limits) |
| **Volumes** | `ai_postgres_data:/var/lib/postgresql/data` (named volume) |
| **Networks** | `db-ai` (internal, isolated from `ai-services`) |
| **Secrets** | `POSTGRES_PASSWORD` (host env var) |
| **Healthcheck** | `pg_isready -U postgres` (10s interval, 5s timeout, 5 retries) |

### Configuration shape

Minimal config surface. Relies on `POSTGRES_PASSWORD` injected at runtime. Database name hardcoded in `litellm` service connection string (`litellm`). No custom `postgresql.conf` overrides visible in compose.

## Dependencies

### Hard (service cannot start or operate without these)
- None (OS networking required only).

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- `litellm` — Hard dependency (`condition: service_healthy`). Fails to start if DB unreachable.
- `openwebui` — Indirect dependency (via `litellm` API).

## State & persistence

- **Database tables / schemas**: LiteLLM internal schema (models, users, keys, proxies, logs).
- **Filesystem state**: `/var/lib/postgresql/data` (named volume `ai_postgres_data`). Growth: Low (KB/MB range for config, GBs only if log retention high).
- **In-memory state**: None (stateless app, stateful disk).
- **External state**: None.
- **Backup status**: ? (No cron/backup job visible in compose).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | <5% | >50% sustained | N/A |
| Memory | ~500MB | >1.5GB | OOM if limit set low |
| Disk I/O | Low (random writes) | High latency | N/A |
| Network | Minimal (internal) | High conn count | N/A |
| Request latency p50 / p95 / p99 | <10ms | >100ms | Timeout |
| Request rate | Low (config churn) | High (burst writes) | Connection pool exhaustion |

## Failure modes

- **Symptom**: `litellm` health check fails (`service_healthy` condition not met).
- **Root cause**: Password env var mismatch, volume corruption, or disk full.
- **Mitigation**: Restart container; verify `POSTGRES_PASSWORD` matches volume state.
- **Prevention**: ? (Backup strategy undefined).

- **Symptom**: `litellm` connects but queries fail.
- **Root cause**: Schema migration mismatch (image upgrade without migration).
- **Mitigation**: Check LiteLLM logs for migration errors.
- **Prevention**: Pin PG version if schema is sensitive (currently `16-alpine`).

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (Current compose supports single instance only).
- **Coordination requirements**: None (Standalone PG).
- **State sharing across replicas**: Shared volume `ai_postgres_data` (cannot be mounted RW on multiple nodes).
- **Hardware bindings**: None (CPU only).
- **Network constraints**: Port 5432 internal to `db-ai` network. No external exposure required.
- **Cluster size constraints**: 1 instance.
- **Migration cost**: Medium. Requires `pg_dump` from `tmtdockp01` to restore on new host. Volume `ai_postgres_data` is bind-mounted or named volume tied to `tmtdockp01`.
- **State durability**: Dependent on ZFS snapshot strategy for `ai_postgres_data` volume (not configured in compose).
- **Failover**: Manual. No automatic promotion of replica exists.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (`last_seen`: 2026-05-01).

### Recurring drift / chronic issues
- ? (Env var `POSTGRES_PASSWORD` management across fleet updates).

### Known sharp edges
- **Volume binding**: If `ai_postgres_data` is a named volume, moving host requires explicit volume copy.
- **Image tag**: `postgres:16-alpine` may pull new patch versions unexpectedly (floating tag).
- **CMDB Criticality**: CMDB marks `critical: false`, but operational dependency from `litellm` makes it functionally critical for AI stack.

## Open questions for Architect

- Why is CMDB `critical: false` when `litellm` depends on it for all routing?
- Backup strategy for `ai_postgres_data` volume (RPO/RTO)?
- Is `postgres:16-alpine` safe to float, or should we pin digest (e.g., `@sha256:...`)?
- Can we tolerate