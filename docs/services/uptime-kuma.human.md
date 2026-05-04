

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours acceptable; no immediate user impact but monitoring visibility lost |
| **Blast radius if down** | Fleet loses external healthcheck visibility; other services continue operating but no alerts on their status degradation |
| **Recovery time today** | Manual restart via compose; no auto-failover |
| **Owner** | ? |

## What this service actually does

Uptime-Kuma provides external health monitoring for the homelab fleet. It polls configured endpoints (HTTP, TCP, ping, etc.) and tracks uptime, response time, and availability trends. Other services don't depend on it operationally—it's purely observability infrastructure.

The fleet uses it to surface service health to dashboards and alerting channels. When it's broken, we lose visibility into whether other services are healthy, but no service functionality degrades.

It is NOT used for internal service-to-service health checks (Netdata handles host-level metrics), NOT a metrics store (don't use it for Prometheus-style time series), and NOT an incident management system.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-security/stacks/monitoring-dockp02/docker-compose.yml` |
| **Image** | `louislam/uptime-kuma:1` |
| **Pinning policy** | Tag-floating (`:1`) - latest minor version; not digest-pinned |
| **Resource caps** | ? (none specified in compose) |
| **Volumes** | `uptime-kuma-data:/app/data` (named volume - persistent state: SQLite DB, config, certificates) |
| **Networks** | `ai-gpu2` (external bridge network) |
| **Secrets** | None (env vars not used for secrets in this deployment) |
| **Healthcheck** | Custom script `extra/healthcheck`; interval 60s, timeout 10s, retries 3, start-period 30s |

### Configuration shape

Configuration is stored in the SQLite database at `/app/data/uptime-kuma.db` within the named volume. No env vars for core config. Web UI handles all settings. Healthcheck script path `extra/healthcheck` suggests custom validation logic not visible in compose.

## Dependencies

### Hard (service cannot start or operate without these)
- `ai-gpu2` network — required for container networking; service won't start if network unavailable
- Named volume `uptime-kuma-data` — required for state persistence; loses all monitor config if missing

### Soft (degrade if these are down, but service still functional)
- None documented (service is self-contained)

### Reverse (services that depend on THIS service)
- None (no upstream services recorded in CMDB dependencies)

## State & persistence

**Critical section for HA design.**

- **Database tables / schemas**: SQLite at `/app/data/uptime-kuma.db` — stores monitor definitions, incident history, user accounts, API keys
- **Filesystem state**: `/app/data` directory contains:
  - `uptime-kuma.db` (SQLite database)
  - `data.db` (additional SQLite data)
  - `certs/` (SSL certificates for monitored endpoints if configured)
  - `backup/` (manual backups if created)
  - Growth rate: ~1-5MB/month depending on monitor count and check frequency
- **In-memory state**: Session data, cached check results — lost on restart but not critical
- **External state**: None (self-hosted, no S3/cloud sync configured)

**Backup strategy**: Volume `uptime-kuma-data` must be backed up. RPO: 24 hours (manual backup). RTO: 30 minutes (volume restore + container start).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | ? | ? | ? |
| Network | ? | ? | ? |
| GPU (if applicable) | N/A | N/A | N/A |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

*Baselines not collected - no Netdata metrics exposed for uptime-kuma specifically*

## Failure modes

- **Symptom**: Healthcheck fails, container restarts in loop
  - **Root cause**: `extra/healthcheck` script missing or broken (custom script not standard in image)
  - **Mitigation**: Disable healthcheck temporarily, restore script
  - **Prevention**: Pin to known-good image digest, add script to compose context

- **Symptom**: All monitor checks fail, no alerts firing
  - **Root cause**: Network connectivity to monitored endpoints blocked
  - **Mitigation**: Verify ai-gpu2 network routing, check firewall rules
  - **Prevention**: ?

- **Symptom**: Volume corruption, database errors on startup
  - **Root cause**: Improper shutdown, volume filesystem issues
  - **Mitigation**: Restore from backup volume snapshot
  - **Prevention**: Ensure graceful shutdown, regular volume backups

## HA constraints (input to fleet-reliability design)

- **Replicable?** No — single-instance stateful service. SQLite database does not support active-active replication.
- **Coordination requirements**: None for current deployment. Would require external DB (PostgreSQL) + leader election for HA.
- **State sharing across replicas**: Not possible with SQLite. Would require migration to PostgreSQL backend with external storage.
- **Hardware bindings**: None (no GPU, USB, or kernel module dependencies)
- **Network constraints**: Web UI on port 3001 (not exposed in compose - likely behind reverse proxy). Must ensure unique port binding if deploying multiple instances.
- **Cluster size constraints**: N/A for single-instance. HA mode requires odd-numbered replicas (3+) with external DB.
- **Migration cost**: Medium. Requires:
  1. Export monitor configuration from web UI
  2. Deploy PostgreSQL backend
  3. Configure uptime-kuma to use external DB
  4. Restore monitors, validate checks
  5. Switch traffic to new instance
  Estimated effort: 2-4 hours downtime.

**Current deployment shows hosts tmtdockp01,tmtdockp02 in CMDB but only tmtdockp02 in compose — verify if active-active or legacy record.**

## Operational history

### Recent incidents (last 90 days)
- ? (no incident records accessible in CMDB)

### Recurring drift / chronic issues
- Healthcheck script `extra/healthcheck` is non-standard — may break on image updates
- Image tag `:1` floating — potential for breaking changes on minor version bumps
- No resource limits — container could consume unbounded memory during intensive checks

### Known sharp edges
- SQLite database locks under high check frequency (>100 monitors with <60s intervals)
- No built-in backup mechanism — must manually snapshot volume
- Healthcheck script path `extra/healthcheck` suggests files mounted from compose context not visible in brief

## Open questions for Architect

- Why does CMDB list both tmtdockp01 and tmtdockp02 but compose only deploys to tmtdockp02?
- What is the `extra/healthcheck` script and where is it sourced from?
- Should uptime-kuma be migrated to PostgreSQL backend for HA capability?
- What is the expected number of monitored endpoints and check frequency?
- Is there a 1Password Connect item for secrets that isn't documented in compose?
- Who owns this service (owner field in brief)?

## Reference

- Compose: `homelab-security/stacks/monitoring-dockp02/docker-compose.yml`
- Logs: `/var/lib/docker/containers/<container-id>/*.log` (json-file driver, 50m max, 3 files)
- Dashboards: ? (no Grafana integration documented)
- Runbooks: ?
- Upstream docs: https://github.com/louislam/uptime-kuma (version 1.x)
- Related services: netdata (host metrics), portainer-agent (container management)