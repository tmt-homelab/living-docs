

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (non-critical media pipeline) |
| **Blast radius if down** | Overseerr 4K requests queue but never process. 4K movie library in Plex (dockp03) stops updating. No new 4K downloads initiated. |
| **Recovery time today** | Auto-restart (`on-failure`). Config restore manual. |
| **Owner** | ? |

## What this service actually does

`radarr-4k` manages metadata and download automation for 4K resolution movies. It operates in parallel with the standard `radarr` instance to separate resolution profiles and indexing rules.

The fleet uses it to bridge Overseerr requests to the download pipeline. It watches `/mnt/media/movies-4k` for completed files and updates the database accordingly. It does NOT manage TV shows (Sonarr) or standard 1080p movies (`radarr`). It does NOT host the Plex database; that resides on `dockp03`.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/radarr:latest` |
| **Pinning policy** | Tag-floating (`latest`) — **Risk:** Unpredictable breaking changes on pull |
| **Resource caps** | ? |
| **Volumes** | `/mnt/docker/radarr-4k:/config` (State), `/mnt/media/movies-4k:/movies-4k` (Data), `/mnt/docker/downloaders:/downloads` (Shared Ingress) |
| **Networks** | `media` (Proxy/Control), `media-download` (Download Clients) |
| **Secrets** | None (Env vars only) |
| **Healthcheck** | `curl -f http://127.0.0.1:7878/ping` (30s interval, 3 retries) |

### Configuration shape

Configuration stored in SQLite DB at `/mnt/docker/radarr-4k/config`. Environment variables define UID/GID (`1000/1000`) and timezone. No dynamic config loading from external secrets.

## Dependencies

### Hard (service cannot start or operate without these)
- **Network `media`** — Required for Caddy reverse proxy communication.
- **Network `media-download`** — Required to reach SABnzbd/NZBGet.
- **`/mnt/docker/downloaders`** — Shared ingress volume for downloaded files. If mounted read-only or missing, service starts but fails to import.
- **`/mnt/docker