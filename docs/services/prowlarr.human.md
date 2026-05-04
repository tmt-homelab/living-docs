

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "hours" (non-critical, config sync only) |
| **Blast radius if down** | Sonarr/Radarr/Radarr-4k lose indexer config updates. Existing searches may fail if they query Prowlarr directly for API calls. |
| **Recovery time today** | auto-restart (`on-failure`) |
| **Owner** | `?` |

## What this service actually does

Prowlarr is an indexer manager for the *arr suite. It centralizes configuration for torrent/NZB indexers and distributes them to Sonarr, Radarr, and Radarr-4k via HTTP API. It manages API keys, proxy settings, and indexer health checks.

Fleet services (Sonarr, Radarr) connect to Prowlarr to fetch indexer definitions. Prowlarr does NOT store media, handle downloads, or manage queues. It is purely a configuration synchronization layer. If Prowlarr is broken, the download clients (SABnzbd/NZBGet) and media libraries (Sonarr/Radarr) continue to function with their last known configuration, but cannot add new indexers or update existing ones.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/prowlarr:latest` |
| **Pinning policy** | tag-floating (`latest`). High risk of breaking changes on pull. |
| **Resource caps** | None defined in compose. |
| **Volumes** | `/mnt/docker/prowlarr:/config` (State: SQLite DB + AppData) |
| **Networks** | `media` (Management/API), `media-download` (Inter-service) |
| **Secrets** | None (API keys stored in local DB) |
| **Healthcheck** | `CMD curl -f http://127.0.0.1:9696/ping` (30s interval, 3 retries) |

### Configuration shape

Environment variables set UID/GID (`1000`) and timezone (`America/Los_Angeles`). No external YAML config file; all configuration is persisted in the SQLite database located in the `/config` volume. Network access is required for external indexers and internal *arr services.

## Dependencies

### Hard (service cannot start or operate without these)
- **Internet Connectivity** — Required to sync with external indexers (Torznab/HDB/API).
- **Docker Daemon** — Required for container runtime.

### Soft (degrade if these are down, but service still functional)
- **Sonarr/Radarr** — Service runs independently, but loses value if consumers are unreachable.
-