

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Seconds to minutes (LiteLLM sessions/cache fail immediately) |
| **Blast radius if down** | LiteLLM health checks fail → Open WebUI auth/session breaks → AI inference routing degrades |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual intervention if data corruption occurs |
| **Owner** | `claude-code` (agent) — requires human handoff for long-term maintenance |

## What this service actually does

In-memory key-value store providing session management and caching for the LiteLLM proxy. It acts as the transient state layer between the API gateway (LiteLLM) and the persistent database (Postgres).

Used by:
- **LiteLLM**: Stores active sessions, API request logs, and rate-limit counters via `REDIS_HOST=redis`.
- **Open WebUI**: Indirectly via LiteLLM for user session persistence.

NOT used for:
- **Model weights**: Those live in `/mnt/docker/ai/models` (ZFS).
- **Vector storage**: That is Milvus (`db-vector` network).
- **Permanent config**: That is Postgres (`db-ai` network).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `redis:8-alpine` |
| **Pinning policy** | Tag-floating (`:8-alpine`). No digest pinning. |
| **Resource caps** | None defined in compose (relies on Docker default cgroups) |
| **Volumes** | `redis_data:/data` (named volume) — **stateful** |
| **Networks** | `ai-services` (internal only) |
| **Secrets** | None (no auth configured in command/env) |
| **Healthcheck** | `redis-cli ping` (interval 30s, timeout 10s, retries 3) |

### Configuration shape
Minimal config surface. Command overrides default to enable AOF persistence (`--appendonly yes`). No password protection configured. Environment variables are empty. Relies on Docker network DNS for hostname resolution (`redis`).

## Dependencies

### Hard (service cannot start or operate without these)
- **None**. Runs standalone on `tmtdockp01`.

### Soft (degrade if these are down, but service still functional)
- **None**. Redis does not depend on other services.

### Reverse (services that depend on THIS service)
- **litellm**: Critical. Fails health check if Redis unreachable. Blocks Open WebUI login/session if down.
- **openwebui**: Indirect dependency via LiteLLM.

## State & persistence

- **Persistence mode**: Append Only File (AOF) enabled.
- **Volume mapping**: `redis_data` named volume mounts to `/data`.
- **Data directory**: `/data/appendonly.aof`.
- **Growth rate**: Low (sessions expire, logs rotate). Monitor disk usage on `tmtdockp01`.
- **Backup strategy**: None configured in compose. Relies on host-level volume backup (`ai_redis_data`).
- **RPO/RTO**:
    - RPO: Minutes (last AOF sync).
    - RTO: Minutes (container restart + volume restore).
- **Replica state**: Single writer. No replication configured. Data loss risk on host failure unless volume is backed up externally.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% (idle) | > 50% sustained | N/A (single core bound) |
| Memory | ~50MB | > 1GB | OOM kill if container limits hit |
| Disk I/O | Low (AOF fsync) | High write latency | Disk full → AOF write fail |
| Network | < 1Mbps | > 100Mbps | Connection timeout |
| Request latency p50/p95 | < 1ms | > 10ms | Queue buildup |
| Request rate | < 100/s | > 5000/s | Client rejection |

## Failure modes

- **Disk Full**: AOF grows indefinitely if `maxmemory` not set. Mitigation: Monitor `df -h` on `/mnt/docker/stacks/ai`.
- **Memory Leak**: If `maxmemory-policy` is missing, Redis grows until OOM. Mitigation: Enforce container memory limits.
- **Network Split**: LiteLLM times out Redis calls. Mitigation: Increase Redis timeout in LiteLLM config.
- **Corruption**: AOF corruption on unclean shutdown. Mitigation: Restore from volume backup; `redis-check-aof`.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (currently single-instance). Supportable (Redis Cluster/Sentinel) but not implemented.
- **Coordination requirements**: None (Standalone mode).
- **State sharing across replicas**: Not applicable (no replicas). State is local to volume `ai_redis_data`.
- **Hardware bindings**: None (CPU/RAM only). Runs on `tmtdockp01` (dockp01).
- **Network constraints**: Internal DNS `redis` must resolve within `ai-services` network. Port 6379 exposed only internally.
- **Cluster size constraints**: N/A (Single node).
- **Migration cost**: High for HA. Moving to Sentinel/Cluster requires:
    1. Provisioning 2+ additional nodes (homelab constraint: limited hardware).
    2. Configuring Sentinel or Cluster mode (requires rewrite of `redis` service in compose).
    3. Updating `litellm` env vars to point to sentinel cluster or load balancer.
    4. Data migration (RDB/AOF transfer).
- **Fleet Risk**: **SPOF**. `tmtdockp01` failure takes down LiteLLM sessions entirely. No failover path to `dockp02` or `dockp03`.

## Operational history

### Recent incidents (last 90 days)
- `2026-04-06` — CMDB registration by `claude-code`. No incidents logged yet.

### Recurring drift / chronic issues
- None observed (service is stable).
- Risk: Volume backup scripts not verified for `redis_data`.

### Known sharp edges
- **Tag Floating**: `redis:8-alpine` may pull breaking changes on `docker compose pull`. No digest pinning.
- **No Auth**: No password set on Redis. Accessible by any container on `ai-services` network.

## Open questions for Architect

- **Backup**: Is there a global volume backup strategy for `ai_redis_data`? If not, RPO is uncontrolled.
- **HA Feasibility**: Does the homelab fleet have hardware capacity for a 3-node Redis Sentinel cluster? (Currently `dockp01` only).
- **Memory Limits**: Should `deploy.resources.limits.memory` be enforced to prevent OOM on `tmtdockp01` during AI load spikes?
- **Auth**: Should `requirepass` be enabled for `ai-services` network security?

## Reference

- Compose: `homelab-ai/stacks/ai/docker-compose.yml`
- Logs: `/var/lib/docker/containers/<id>/*.log` (json-file, 50m)
- Dashboards: ? (No Grafana datasource configured)
- Runbooks: `homelab-ai/runbooks/redis-re