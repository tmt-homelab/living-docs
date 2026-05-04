

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (Non-critical monitoring) |
| **Blast radius if down** | Plex continues functioning. Analytics/history visibility lost. No impact on media playback or download pipelines. |
| **Recovery time today** | Auto-restart (`on-failure`) + Container replacement |
| **Owner** | ? |

## What this service actually does

Tautulli polls the Plex Media Server API to collect playback statistics, user activity, and library metadata. It serves as the observability layer for the media fleet, providing historical graphs and alerting on concurrent streams.

Other services do not consume Tautulli data. It is a read-only consumer of Plex telemetry. It does not manage downloads, transcode media, or handle authentication for the media servers.

When broken, operators lose visibility into "who is watching what" and cannot audit library usage. The core media delivery stack (Plex, *arrs, download clients) remains unaffected.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/tautulli:latest` |
| **Pinning policy** | `tag-floating` (latest) — Risk of breaking changes on upstream release |
| **Resource caps** | Not defined (Defaults to host limits) |
| **Volumes** | `/mnt/docker/tautulli:/config` (State: DB + Config) |
| **Networks** | `media` (External bridge) |
| **Secrets** | None (Auth handled via Web UI session / API key in config) |
| **Healthcheck** | `curl -f http://127.0.0.1:8181/status` (30s interval, 3 retries) |

### Configuration shape

Configuration is persisted entirely inside the container volume (`/config`).
- **Web UI**: Primary management interface.
- **Config File**: `config.ini` (XML-based) inside volume.
- **Environment**: Only `PUID`, `PGID`, `TZ` are injected. No feature flags via env.

## Dependencies

### Hard (service cannot start or operate without these)
- **Plex Media Server** (Host: `dockp03`) — Tautulli cannot populate data without active polling of the Plex API. Network connectivity between `dockp04` and `dockp03` is required.
- **Docker Daemon** — Standard runtime dependency.

### Soft (degrade if these are down, but service still functional)
- **Caddy Reverse Proxy** — Tautulli is exposed via `media` network. If Caddy is down, external access fails, but internal healthchecks pass.

### Reverse (services that depend on THIS service)
- **None** — No downstream fleet services consume Tautulli APIs.

## State & persistence

**Primary State Location:** `/mnt/docker/tautulli`

- **Database:** `tautulli.db` (SQLite). Stores all historical play logs, user stats, and notification logs.
- **Config:** `config.ini`. Contains API keys for Plex, webhook URLs, and UI settings.
- **Logs:** Internal logs (`logs/` dir) and Docker stdout (json-file).
- **Growth:** Linear. Depends on media library size and playback frequency. Can reach GBs over years if not archived.
- **Backup Strategy:** Full directory backup required. DB must be consistent (Tautulli locks DB during writes).
- **Replication:** Not supported. State is local to `dockp04`.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? (Typically <5%) | >80% sustained | Throttles polling frequency? |
| Memory | ? (Typically <256MB) | >512MB | GC cycles increase |
| Disk I/O | Low (DB writes) | High sustained writes | DB locks may cause UI lag |
| Network | Low (Polling) | High (Web traffic) | N/A |
| Request latency p50 | ? | >2s | Timeout errors |
| Request rate | ? | ? | N/A |

## Failure modes

- **Plex API Drift**: Plex updates may break Tautulli parsing logic.
  - *Symptom*: Data gaps in dashboard, "API Error" alerts.
  - *Mitigation*: Rollback Tautulli image tag.
  - *Prevention*: Pin image digest (currently `:latest`).
- **SQLite Corruption**: Improper shutdown or disk failure.
  - *Symptom*: Web UI returns 500, DB locked errors.
  - *Mitigation*: Restore `tautulli.db` from backup.
- **Disk Full**: Log rotation misconfiguration or DB bloat.
  - *Symptom*: Container restarts, config writes fail.
  - *Prevention*: Monitor `/mnt/docker` partition usage.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No.
- **Coordination requirements**: None.
- **State sharing across replicas**: N/A (Single instance).
- **Hardware bindings**: None.
- **Network constraints**:
  - Must have egress to `dockp03` (Plex host) on port 32400.
  - Must be reachable by Caddy via `media` network.
- **Cluster size constraints**: N/A.
- **Migration cost**: **High**. Moving to a new host requires:
  1. Copying `/mnt/docker/tautulli` volume.
  2. Ensuring new host has network path to Plex (`dockp03`).
  3. Updating Caddy proxy config if host IP changes.
- **Critical Design Note**: This service breaks the "stateless" ideal. It is a stateful monitor of an external system. It cannot be load-balanced. If `dockp04` fails, monitoring stops until restored on new host.

## Operational history

### Recent incidents (last 90 days)
- ?

### Recurring drift / chronic issues
- ?

### Known sharp edges
- **Latest Tag Risk**: Image uses `:latest`. Upstream changes may introduce breaking API changes for Plex communication.
- **Cross-Host Dependency**: Tautulli (`dockp04`) relies on Plex (`dockp03`). Network partition between these nodes kills data ingestion.

## Open questions for Architect

- Should we pin the image to a specific digest or version tag to prevent breaking changes during Plex updates?
- What is the acceptable RPO for the Tautulli database? (History loss vs. Availability)
- Is there a strategy to replicate Tautulli state to `dockp03` for failover? (Likely not worth the complexity for non-critical service).

## Reference

- Compose: `homelab-media/stacks/dockp04-media/docker-compose.yml`
- Logs: `/var/lib/docker/containers/<id>/<id>-json.log` (Docker daemon), `/mnt/docker/tautulli/logs/` (Internal)
- Dashboards: ?
- Runbooks: ?
- Upstream docs: https://tautulli.com/
- Related services: `plex` (dockp03-plex stack), `overseerr` (dockp04-media stack)