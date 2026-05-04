

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (secrets unavailable blocks deployments/autodeps) |
| **Blast radius if down** | All services consuming secrets via `op-connect-sync` fail auth/decryption. CI/CD pipelines halt if secret injection fails. |
| **Recovery time today** | Auto-restart (`unless-stopped`), but data volume lock contention may require manual intervention. |
| **Owner** | `claude-code` (Automated registration) / Homelab Ops |

## What this service actually does

`op-connect-api` exposes the 1Password Connect HTTP API. It serves as the local interface for other containers to fetch secrets from 1Password Cloud.

The fleet uses it in tandem with `op-connect-sync`. The `sync` component pulls vault data from 1Password Cloud and caches it locally. The `api` component serves that cached data to consumers on the `secrets` network.

This service is NOT used for direct CLI interaction by humans (use `op` binary). It is NOT a general purpose secrets manager (does not support arbitrary KV stores outside 1Password schema). It does not encrypt data at rest independently; it relies on the 1Password encryption layer.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/misc/docker-compose.yml` |
| **Image** | `1password/connect-api:latest` |
| **Pinning policy** | Tag-floating (`latest`). High risk for unexpected upstream changes. |
| **Resource caps** | ? (Not defined in compose) |
| **Volumes** | `op-connect-data` (State, named), `/mnt/docker/1password-connect/1password-credentials.json` (Read-only secrets) |
| **Networks** | `secrets` (External) |
| **Secrets** | `1password-credentials.json` (Mounted at `/home/opuser/.op/1password-credentials.json`) |
| **Healthcheck** | `connect-api --version` (Exec). Checks process existence, not liveness. |

### Configuration shape

Configuration is primarily driven by the mounted credentials file. Environment variables (e.g., `OP_CONNECT_TOKEN`) are typically injected via the credentials JSON or env block (not visible in current snippet). No external YAML config files are exposed.

## Dependencies

### Hard (service cannot start or operate without these)
- **1Password Cloud** — Sync component requires this to refresh data. If unreachable, data becomes stale.
- **Volume `op-connect-data`** — API reads from here. If missing, API starts but returns empty/invalid state.
- **`op-connect-sync`** — Logical dependency. Without sync, data is never refreshed. Shared volume creates coupling.

### Soft (degrade if these are down, but service still functional)
- **Network `secrets`** — API remains up, but consumers cannot reach it.

### Reverse (services that depend on THIS service)
- **Fleet Secrets Consumers** — Any container accessing `1password-credentials.json` pattern or querying the API on `secrets` network. Breakage: Application auth failures.

## State & persistence

- **Database tables / schemas:** ? (Internal SQLite/LevelDB inside container volume)
- **Filesystem state:** `op-connect-data` volume (`/home/opuser/.op/data`). Contains cached vault items, tokens, and metadata.
    - Growth rate: Low (depends on vault size).
    - Backup: Must be included in volume backup strategy.
- **In-memory state:** Runtime cache. Lost on restart (recovered from volume).
- **External state (S3, etc.):** None.

**Critical Note:** The `op-connect-data` volume is mounted read-write by BOTH `op-connect-api` and `op-connect-sync`. This creates a strict FS-level coupling.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | ? | ? | ? |
| Network | ? | ? | ? |
| GPU (if applicable) | None | N/A | N/A |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Volume Lock Contention**
    - **Symptom:** API 500 errors, Sync fails to write.
    - **Root cause:** API and Sync both writing to `op-connect-data` simultaneously without distributed locking.
    - **Mitigation:** Restart both containers.
    - **Prevention:** Ensure single instance deployment.

- **Token Expiration**
    - **Symptom:** `401 Unauthorized` from API.
    - **Root cause:** `1password-credentials.json` token expired.
    - **Mitigation:** Regenerate token in 1Password CLI, update mount.
    - **Prevention:** Monitor token expiry via external script.

- **Tag Drift**
    - **Symptom:** Unexpected config changes after `docker-compose pull`.
    - **Root cause:** Image tag `latest` floating.
    - **Mitigation:** Pin to digest in compose.
    - **Prevention:** CI pipeline enforces digest pinning.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No.
- **Coordination requirements:** None (but requires exclusive FS access).
- **State sharing across replicas:** **Shared named volume `op-connect-data`**. This volume is mounted into both `op-connect-api` and `op-connect-sync`. Standard Kubernetes volume claims or NFS sharing for this specific 1Password Connect pair is unsupported/risky without specific config.
- **Hardware bindings:** None.
- **Network constraints:** Must be attached to `secrets` network. No specific ports exposed to host (internal comms).
- **Cluster size constraints:** Strictly 1 instance. Running multiple `op-connect-api` containers against the same `op-connect-data` volume will cause data corruption.
- **Migration cost:** High. To enable HA, must decouple API state from Sync state (requires upstream feature or proxy layer). Currently, moving to a cluster requires manual data migration and potential downtime.
- **Failover strategy:** Active-Passive via external load balancer is not viable due to FS lock requirements. Requires external health check to swap single IP.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB.

### Recurring drift / chronic issues
- None known.

### Known sharp edges
- **Sync/API coupling:** Do not restart `op-connect-api` without `op-connect-sync` running; Sync is required to maintain data freshness.
- **Image Tags:** `latest` tag in `homelab-core/stacks/misc/docker-compose.yml` is a stability risk for production-like workloads.

## Open questions for Architect

- ? (Can we migrate to a pinned digest without breaking the homelab GitOps flow?)
- ? (Is there a supported pattern for HA 1Password Connect in a cluster environment, or is single-instance acceptable for this fleet?)
- ? (Backup strategy for `op-connect-data` volume: snapshot vs. file copy?)

## Reference

- Compose: `homelab-core/stacks/misc/docker-compose.yml`
- Logs: `docker logs op-connect-api` (JSON-file driver, 50m max size, 3 files)
- Dashboards: ?
- Runbooks: ?
- Upstream docs: https://developer.1password.com/docs/connect/
- Related services: `op-connect-sync` (shared volume dependency)