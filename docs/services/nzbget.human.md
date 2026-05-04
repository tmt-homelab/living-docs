

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (media acquisition stalls, no core infra impact) |
| **Blast radius if down** | Sonarr/Radarr cannot process NZB requests. Download pipeline halts for Usenet content. |
| **Recovery time today** | Auto-restart (`restart: on-failure`) |
| **Owner** | ? |

## What this service actually does

NZBGet is the primary Usenet download client for the `media-download` pipeline. It accepts NZB files (metadata) from Prowlarr and arr-family services (Sonarr, Radarr), resolves the binary segments, verifies integrity, and writes completed files to the shared download volume.

It operates in tandem with Sabnzbd. While Sabnzbd handles general NZB traffic, NZBGet is configured for high-speed Usenet retrieval where supported. It exposes a Web UI and API on port 6789 for configuration, queue management, and API polling by automation tools.

This service is **NOT** used for torrenting (qBittorrent/Transmission not in scope here) and is **NOT** the metadata manager (that is Sonarr/Radarr). It does not store media long-term; it acts as a transit buffer before post-processing scripts move files to `/mnt/media`.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/nzbget:latest` |
| **Pinning policy** | Tag-floating (`:latest`). Risk: Upstream may introduce breaking changes without warning. |
| **Resource caps** | None defined (relies on host limits) |
| **Volumes** | `/mnt/docker/nzbget:/config` (State), `/mnt/docker/downloaders:/downloads` (Shared Data) |
| **Networks** | `media` (UI/API), `media-download` (Isolation from public-facing services) |
| **Secrets** | ? (Credentials stored in config file, not env/secrets manager) |
| **Healthcheck** | `curl -f http://127.0.0.1:6789` (Root URL check, no specific `/ping` endpoint) |

### Configuration shape

Configuration is primarily file-based (`/config/nzbget.conf`). Environment variables are limited to user IDs and timezone (`PUID`, `PGID`, `TZ`). The API token is stored in the config file. No dynamic config reload via env