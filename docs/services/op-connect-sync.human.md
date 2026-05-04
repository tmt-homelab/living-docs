

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (Single-instance stateful per host) |
| **Tolerable outage** | ~15 minutes (Sync interval dependent) |
| **Blast radius if down** | `op-connect-api` returns stale secrets or 503. Services mounting secrets via Connect SDK fail auth/config load. |
| **Recovery time today** | Auto-restart (Docker), manual intervention for volume corruption |
| **Owner** | ? (CMDB registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Synchronizes secrets from 1Password Cloud to a local SQLite database. It acts as the write-behind cache for the 1Password Connect ecosystem. The fleet consumes secrets via `op-connect-api`, which reads from the DB populated by this sync service.

When this service is healthy, the local data volume reflects the current state of the 1Password vault (within the sync interval). When broken, the API serves stale data or fails to authenticate requests to 1Password Cloud.

It is **NOT** a user-facing secret manager (no UI). It is **NOT** an authentication provider (no OIDC/OAuth). It is strictly a synchronization daemon.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/misc/docker-compose.yml` |
| **Image** | `1password/connect-sync:latest` |
| **Pinning policy** | Tag-floating (`latest`) — Risky for secrets service |
| **Resource caps** | ? (Not defined in compose) |
| **Volumes** | `/mnt/docker/1password-connect/1password-credentials.json:ro` (Bind mount), `op-connect-data:/home/opuser/.op/data` (Named volume, shared with `op-connect-api`) |
| **Networks** | `secrets` (External), `egress` (External) |
| **Secrets** | 1Password Connect API credentials (mounted via JSON file) |
| **Healthcheck** | `CMD connect-sync --version` (Static binary check, does not verify sync status) |

### Configuration shape

No YAML config file. Configuration is entirely environment-driven via 1Password Connect standard env vars (usually injected or mounted). The service relies on the mounted `1password-credentials.json` for authentication to the 1Password Cloud API.

## Dependencies

### Hard (service cannot start or operate without these)
- **1Password Cloud API** — Egress required on port 443. Without this, sync fails silently until retry.
- **`op-connect-api`** — Co-located requirement. They share the `op-connect-data` named volume. If API is on Host A and Sync on Host B, data is partitioned/corrupted.
- **`secrets` network** — Internal routing for API to Sync communication (if applicable) or just general container isolation.

### Soft (degrade if these are down, but service still functional)
- **Egress gateway** — If `egress` network is blocked, sync stops, but cached secrets remain available in DB.

### Reverse (services that depend on THIS service)
- **`op-connect-api`** — Reads the DB populated by this service. If Sync is down, API serves stale data.
- **Secret-consuming applications** — Any container configured to fetch secrets via Connect SDK/API.

## State & persistence

- **Database tables / schemas:** SQLite database located at `/home/opuser/.op/data` inside container (mapped to `op-connect-data` volume). Contains secret key-value pairs and metadata.
- **Filesystem state:** `1password-credentials.json` (Bind mount, read-only). Must exist on host filesystem at `/mnt/docker/1password-connect/`.
- **In-memory state:** Sync job state, connection pools. Lost on restart but recoverable from Cloud.
- **External state:** 1Password Cloud (Source of Truth).
- **Backup:** `op-connect-data` volume must be backed up. Snapshotting while running risks SQLite corruption.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | > 50% sustained | N/A |
| Memory | ? | > 1GB | N/A |
| Disk I/O | Low (Periodic writes) | High write latency | N/A |
| Network | Bursty (Sync interval) | Constant high throughput | N/A |
| GPU | None | ? | N/A |
| Request latency p50 / p95 / p99 | N/A (Background process) | ? | N/A |
| Request rate | 0 (No external API) | ? | N/A |

## Failure modes

- **Symptom:** Secrets not updating. **Root cause:** Egress blocked or 1Password Cloud auth expired. **Mitigation:** Check `op-connect-sync` logs for 401/403. **Prevention:** Rotate credentials before expiry.
- **Symptom:** Service healthy but secrets stale. **Root cause:** Healthcheck only checks binary version, not connectivity. **Mitigation:** Replace healthcheck with HTTP endpoint check if available. **Prevention:** Update compose definition.
- **Symptom:** Crash loop. **Root cause:** Volume permission issues or SQLite lock. **Mitigation:** Check host volume ownership. **Prevention:** Ensure `op-connect-api` is stopped before migrating volumes.
- **Symptom:** Data