

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 24 hours |
| **Blast radius if down** | User request pipeline stalls. Sonarr/Radarr/Plex unaffected. No media loss, only metadata/request metadata loss. |
| **Recovery time today** | Auto-restart (`restart: on-failure`). Config restore requires DB backup. |
| **Owner** | `Unknown` (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Overseerr acts as the self-service request portal for the media fleet. It provides a UI for users to browse the Plex catalog (synced from Plex) and request new content. When a request is approved, Overseerr triggers API calls to Sonarr (TV) or Radarr (Movies) to initiate downloads via the download clients.

It is NOT a media server. It does not serve content, nor does it manage download queues directly. It is a stateful metadata aggregator. It stores user requests, approval logs, and API keys for downstream services.

Other fleet services consume Overseerr primarily for status webhooks (Radarr/Sonarr update request status back to Overseerr). End-users consume the HTTP API/UI. If Overseerr is down, users cannot request content, but existing downloads and playback continue normally.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `seerr/seerr:latest` |
| **Pinning policy** | Tag-floating (`latest`). High risk of breaking changes. |
| **Resource caps** | None defined in compose. |
| **Volumes** | `/mnt/docker/overseerr:/app/config` (State: SQLite DB, logs, cache) |
| **Networks** | `media` (Internal API comms), `vlan200` (External/UI access) |
| **Secrets** | None in compose. API keys likely stored in config DB. |
| **Healthcheck** | `wget -q --spider http://127.0.0.1:5055/api/v1/status` (30s interval) |

### Configuration shape

Configuration is stored in SQLite within the `/app/config` volume. Environment variables control runtime parameters (`PUID`, `PGID`, `TZ`). API keys for Sonarr/Radarr/Plex are stored encrypted in the local database, not as env vars. No external config file mounting; UI-driven configuration is the primary surface.

## Dependencies

### Hard (service cannot start or operate without these)
- **Network `media`**: Required to reach Sonarr/Radarr/Plex APIs. Without this, request creation fails silently or errors out.
- **Network `vlan200`**: Required for external user access (assuming Caddy routes here).

### Soft (degrade if these are down, but service still functional)
- **Sonarr/Radarr**: Overseerr UI loads, but "Request" buttons fail. Status indicators show error.
- **Plex**: Overseerr cannot verify media availability or refresh library without Plex API.

### Reverse (services that depend on THIS service)
- **End-users**: Cannot request media.
- **Sonarr/Radarr**: Do not depend on Overseerr for operation, but lose request status sync.

## State & persistence

State is critical for user tracking. All state is local to the container volume.

- **Database**: SQLite file (`database.db`) in `/app/config`. Contains user accounts, requests, API keys, settings.
- **Filesystem state**: `/app/config/logs` (App logs), `/app/config/cache` (Image caching).
- **In-memory state**: Session tokens, in-flight request processing queues (lost on restart).
- **External state**: None. No S3/Cloud storage for config.
- **Backup Strategy**: Volume `/mnt/docker/overseerr` must be included in host-level backup jobs. RPO: 24h (daily backup assumed). RTO: 15m (restore + restart).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 50% sustained | Degraded API response |
| Memory | < 256MB | > 700MB | OOM Kill |
| Disk I/O | Low (DB writes on request) | High continuous | DB Lock contention |
| Network | < 10Mbps (Image fetches) | > 100Mbps | Proxy timeout |
| Request latency p95 | < 200ms | > 2s | Timeout (504) |
| Request rate | < 10 req/min | > 100 req/min | Rate limit |

## Failure modes

- **Symptom**: Healthcheck fails, but container stays running.
  - **Root cause**: App process hung; `wget` spider check passed but app logic dead.
  - **Mitigation**: Restart container.
  - **Prevention**: Improve healthcheck to verify DB connection, not just HTTP 200.

- **Symptom**: Requests fail with 500 error.
  - **Root cause**: Radarr/Sonarr API keys rotated externally; Overseerr DB holds stale creds.
  - **Mitigation**: Re-enter API keys in UI.
  - **Prevention**: Store keys in secrets manager, not DB.

- **Symptom**: Container exits immediately.
  - **Root cause**: `seerr/seerr` image pulled breaking change (`latest` tag).
  - **Mitigation**: Pin to previous digest or switch image source.
  - **Prevention**: Pin image digest.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. SQLite DB locks prevent concurrent writes across replicas.
- **Coordination requirements**: