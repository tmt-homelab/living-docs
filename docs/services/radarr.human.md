

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 24h (non-critical media fetching) |
| **Blast radius if down** | Overseerr requests fail to trigger downloads; Plex library metadata not updated; movie queue stalls |
| **Recovery time today** | Auto-restart (`on-failure`) via Docker; manual intervention if config DB corrupt |
| **Owner** | `phase-1.4-bulk-backfill` (agent) / ? (human) |

## What this service actually does

Manages movie metadata, availability tracking, and download coordination for the media fleet. It does not store video files itself; it tracks paths in `/mnt/media/movies`.

The fleet uses it for:
- Indexer integration via Prowlarr (internal network).
- Download handoff to SABnzbd/NZBGet via shared filesystem `/mnt/docker/downloaders`.
- Library metadata updates sent to Plex (indirectly, via file system changes).

It is NOT used for:
- Video transcoding (Plex handles this).
- Actual downloading (download clients handle this).
- 4K movie tracking (handled by sibling service `radarr-4k` on same host).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/radarr:latest` |
| **Pinning policy** | Tag-floating (`latest`) — risky for stability, no digest lock |
| **Resource caps** | Unknown (no limits set in compose) |
| **Volumes** | `/mnt/docker/radarr:/config` (State), `/mnt/media/movies:/movies` (Content), `/mnt/docker/downloaders:/downloads` (Handoff) |
| **Networks** | `media` (proxy), `media-download` (internal API) |
| **Secrets** | None (credentials stored in `/config` DB) |
| **Healthcheck** | `curl -f http://127.0.0.1:7878/ping` (30s interval, 10s timeout, 3 retries) |

### Configuration shape

Environment variables (`PUID`, `PGID`, `TZ`) only. All application config stored in SQLite DB within `/mnt/docker/radarr`. No external YAML config surface exposed.

## Dependencies

### Hard (service cannot start or operate without these)
- None (process starts independently of network state).

### Soft (degrade if these are down, but service still functional)
- `prowlarr` — Indexer API unavailable; no new search results.
- `sabnzbd` / `nzbget` — Download execution fails; queue builds up.
- `/mnt/docker/downloaders` — Handoff fails if mount missing or perms wrong.

### Reverse (services that depend on THIS service)
- `overseerr` — Request approval flows to Radarr.
- `plex` — Library updates rely on new files appearing in `/mnt/media/movies`.

## State & persistence

State is critical. Loss of `/config` volume means total loss of movie metadata and configuration.

- **Database**: SQLite DB at `/config/database.db` (implied