

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (non-critical media automation) |
| **Blast radius if down** | New show tracking halts; automated downloads stop; Overseerr request integration fails. Existing media playback unaffected. |
| **Recovery time today** | Auto-restart (`on-failure`) for process crashes; manual restore for config corruption. |
| **Owner** | ? (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Sonarr monitors RSS feeds for TV shows, manages download queues via integrated clients, and organizes completed files into `/mnt/media/tv`. The fleet uses it as the control plane for TV media ingestion. It exposes an HTTP API (8989) for configuration and status, and a REST API for external integrations (Overseerr, Prowlarr).

It is NOT a media player (Plex handles playback on dockp03). It is NOT a download engine (Sabnzbd/NzbGet handle bitstreams). It does NOT store media content itself, only metadata and file path mappings.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/sonarr:latest` |
| **Pinning policy** | Tag-floating (`:latest`) — risk of breaking changes on upstream rebuild. |
| **Resource caps** | None defined in compose. |
| **Volumes** | `/mnt/docker/sonarr:/config` (State), `/mnt/media/tv:/tv` (Media), `/mnt/docker/downloaders:/downloads` (Shared scratch) |
| **Networks** | `media` (Web/API), `media-download` (Internal RPC to download clients) |
| **Secrets** | None (Auth handled via HTTP Basic/Session in config) |
| **Healthcheck** | `curl -f http://127.0.0.1:8989/ping` (30s interval, 3 retries) |

### Configuration shape

Config lives in `/config` inside the container. Database is SQLite (`sonarr.db`). Environment variables set PUID/PGID for filesystem permission mapping and timezone. No external YAML config file; all settings persisted in DB within the config volume.

## Dependencies

### Hard (service cannot start or operate without these)
- **Docker Engine** — Container runtime.
- **`/mnt/docker/sonarr`** — Config volume (contains SQLite DB).
- **`/mnt/media/tv`** — Target media directory (write access required).
- **`/mnt/docker/downloaders`** — Download staging directory (read/write).

### Soft (degrade if these are down, but service still functional)
- **Prowlarr** — Indexers unavailable; search functionality fails.
- **Sabnzbd/NzbGet** — Download queue stalls; Sonarr marks downloads as "Failed".
- **Overseerr** — Request button unavailable; request flow breaks.

### Reverse (services that depend on THIS service)
- **Overseerr** — Checks availability/monitoring status via Sonarr API.
- **Radarr** — Co-located, no direct dependency but shares `/downloads` volume (potential contention).

## State & persistence

- **Database tables / schemas**: SQLite `sonarr.db` in `/config`. Contains show metadata, season files, download history, API keys.
- **Filesystem state**: `/config` contains logs and DB. `/mnt/docker/downloaders` contains incomplete downloads (managed by download client, but Sonarr watches for completion).
- **In-memory state**: Download queue state, RSS cache. Lost on restart (recovered from DB if persistent).
- **External state**: None (all metadata local).

**Backup Requirement**: `/mnt/docker/sonarr` must be backed up daily. `/mnt/media/tv` is assumed backed up via NAS snapshot (not Sonarr scope).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 5-10% | > 80% sustained | CPU throttles import tasks |
| Memory | 256-512MB | > 1GB | OOM kill if unmanaged |
| Disk I/O | Low (polling) | High during import | Write contention on `/downloads` |
| Network | < 10Mbps (API) | > 100Mbps (RSS flood) | API latency spikes |
| GPU | N/A | N/A | N/A |
| Request latency p50 / p95 / p99 | 50ms / 150ms / 500ms | > 2s | UI becomes unresponsive |
| Request rate | 1-5 req/min | > 100 req/min | Rate limiting triggers |

## Failure modes

- **Symptom**: Healthcheck fails. **Root cause**: Docker network isolation issue or process crash. **Mitigation**: `docker compose up -d sonarr`. **Prevention**: Watch `restart: on-failure` logs.
- **Symptom**: Import fails silently. **Root cause**: Permission mismatch (PUID/PGID 1000 vs host FS). **Mitigation**: `chown -R 1000:1000 /mnt/docker/sonarr`. **Prevention**: Enforce PUID/PGID consistency across fleet.
- **Symptom**: Download queue stalls. **Root cause**: Download client unreachable on `media-download` network. **Mitigation**: Check `media-download` network bridge health. **Prevention**: Verify firewall rules between containers.
- **Symptom**: DB Corruption. **Root cause**: Unclean shutdown during write. **Mitigation**: Restore from `/mnt/docker/sonarr` backup. **Prevention**: Use `:degraded` disk mode or UPS.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Sonarr is designed for single-instance deployment. Active/Active clustering is not supported natively.
- **Coordination requirements**: None.
- **State sharing across replicas**: Impossible without externalizing the SQLite DB (requires migration to PostgreSQL/MySQL, not supported by `linuxserver` image).
- **Hardware bindings**: None. Runs on generic x86_64/ARM64.
- **Network constraints**: Internal API port 8989 must be unique per