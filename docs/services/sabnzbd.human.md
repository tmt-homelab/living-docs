

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours acceptable; breaks automation pipeline (Radarr/Sonarr stalls) |
| **Blast radius if down** | Radarr/Sonarr cannot fetch content; Prowlarr indexers lose download target; queue stalls |
| **Recovery time today** | Auto-restart (`on-failure`) + manual intervention for queue corruption |
| **Owner** | `?` (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Downloads NZB files from Usenet providers, manages queue state, and handles post-processing (unpack, repair, verify). The fleet uses it as the ingestion point for the `media-download` pipeline. Radarr and Sonarr push download tasks here; completed files land in `/mnt/docker/downloaders` for consumption.

It is NOT an indexer (Prowlarr handles that), NOT a media server (Plex handles that), and NOT a request portal (Overseerr handles that). It is strictly a download agent.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp04-media/docker-compose.yml` |
| **Image** | `lscr.io/linuxserver/sabnzbd:latest` |
| **Pinning policy** | Tag-floating (`:latest`) — risk of breaking changes on rebuild |
| **Resource caps** | None defined in compose (unbounded CPU/Mem) |
| **Volumes** | `/mnt/docker/sabnzbd:/config` (state), `/mnt/docker/downloaders:/downloads` (shared state) |
| **Networks** | `media` (Caddy proxy), `media-download` (internal arr comms) |
| **Secrets** | None (API keys stored in config volume) |
| **Healthcheck** | `CMD curl -f http://127.0.0.1:8080/api?mode=version` (30s interval, 10s timeout) |

### Configuration shape

Config stored in `/mnt/docker/sabnzbd`. Environment variables control PUID/PGID (1000/1000) and TZ. API key and server connections stored in `sabnzbd.ini` inside config volume. Download directories point to host paths.

## Dependencies

### Hard (service cannot start or operate without these)
- **Usenet Provider Connectivity** — External internet access required for binary retrieval.
- **Network `media-download`** — Required for Radarr/Sonarr to reach download API.

### Soft (degrade if these are down, but service still functional)
- **Prowlarr** — If down, cannot update indexer list or fetch new NZBs automatically.

### Reverse (services that depend on THIS service)
- **Radarr / Radarr-4k** — Push download tasks; fail if download client API is unreachable.
- **Sonarr** — Push download tasks; fail if download client API is unreachable.
- **Prowlarr** — Pushes download links; expects status callbacks.

## State & persistence

- **Database tables / schemas**: SQLite DB embedded in config volume (`queue.db`, `history.db`). Critical for active download state.
- **Filesystem state**: 
  - `/mnt/docker/sabnzbd`: Config and DB. RPO: Daily backup recommended.
  - `/mnt/docker/downloaders`: Active downloads and completed files. High churn.
- **In-memory state**: Active download progress buffers. Lost on restart, but DB usually persists queue.
- **External state**: None (local Usenet cache only).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 5-10% | >80% sustained | Spikes during unpack/PAR2 repair |
| Memory | 500MB | >2GB | Swap pressure if cache fills |
| Disk I/O | High Write (download) / High Read (unpack) | >90% Utilization | Queue stalls on disk full |
| Network | Variable (depends on slot) | N/A | Bandwidth capped by upstream provider |
| GPU | 0% | N/A | Not used |
| Request latency p50 | <50ms | >2s | UI unresponsive during heavy I/O |
| Request rate | Low (API polling) | N/A | N/A |

## Failure modes

- **Symptom**: Healthcheck fails (curl timeout).
  - **Root cause**: Main process hung or OOM.
  - **Mitigation**: `docker restart sabnzbd`.
  - **Prevention**: Set memory limits; monitor disk usage.

- **Symptom**: Downloads stall at 0%.
  - **Root cause**: Disk full or permission error on `/downloads`.
  - **Mitigation**: Clear old files; check `PUID/PGID` match host.
  - **Prevention**: Alert on volume >90%.

- **Symptom**: Completed files missing from Radarr/Sonarr.
  - **Root cause**: Folder naming mismatch or permissions blocking move.
  - **Mitigation**: Manual move to watch folder.
  - **Prevention**: Verify `complete_dir` config matches `download_dir` structure.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Active downloads cannot be split across nodes without shared filesystem locking which causes corruption.
- **Coordination requirements**: None. Single node leader.
- **State sharing across replicas**: **Critical Constraint.** `/mnt/docker/downloaders` is a shared volume. If a second instance starts, it risks file lock conflicts on incomplete parts (`*.par2`, `*.nzb`). Queue state (`queue.db`) is not designed for concurrent writes.
- **Hardware bindings**: None (no USB/GPU passthrough).
- **Network constraints**: Internal port 8080 must remain unique. External access via Caddy on `media` network.
- **Cluster size constraints**: Strictly 1 instance per host. Cannot run active-active on same shared download volume.
- **Migration cost**: High. Moving active queue requires stopping service, copying DB, ensuring file integrity, and restarting. Queue state loss is acceptable but causes user friction.
- **Failover capability**: Manual. If `tmtdockp04` dies, must spin up on new host and reconfigure Usenet credentials. Cannot auto-failover queue.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (last seen `2026-05-01`).

### Recurring drift / chronic issues
- **Permissions**: `PUID=1000` conflicts if host user is different. Requires `chown` on `/mnt/docker/sabnzbd` after host changes.
- **Disk Space**: `/downloads` fills up if cleanup scripts fail, blocking new downloads.

### Known sharp edges
- **Tag Floating**: `:latest` tag may pull breaking API changes during auto-update. Pin digest in prod.
- **Config Lock**: If `sabnzbd.ini` is locked by process during crash, manual unlock needed.

## Open questions for Architect

- ? Can `/mnt/docker/downloaders` be moved to a networked storage (NFS) to allow easier host migration? (Risk: File locking latency)
- ? Is there a backup strategy for `queue.db` specifically, or just the whole config volume?
- ? Should we pin `linuxserver/sabnzbd` to a specific digest to prevent breaking changes?

## Reference

- Compose: `hom