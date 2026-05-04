

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | 1-2 hours (media buffering tolerated, but user experience degraded) |
| **Blast radius if down** | All media consumption stops. DLNA/HomeKit discovery fails immediately. Clients cache metadata but fail playback. |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual NFS mount recovery if `tmtdockp04` fails. |
| **Owner** | `tmttodd` (Git repo owner) |

## What this service actually does

Plex Media Server indexes and streams media files from NFS mounts to client devices. It performs real-time video transcoding using the A5000 GPU on `tmtdockp03`. The fleet uses it as the central media library for DLNA, HomeKit, and direct HTTP playback.

It is **not** a storage backend. Media files are mounted read-only from `tmtdockp04`. Plex does not write media data back to the NFS share; write operations are limited to configuration, metadata, and transcode scratch space on local ZFS. It is not used for file sharing or backup services.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/dockp03-plex/docker-compose.yml` |
| **Image** | `plexinc/pms-docker:latest` |
| **Pinning policy** | Tag-floating (`latest`). Risk: upstream schema changes may break compatibility. No digest pinning in current config. |
| **Resource caps** | GPU: `runtime: nvidia` (GPU 0). No explicit CPU/Mem limits defined in compose. |
| **Volumes** | **State**: `/mnt/docker/plex/config` (ZFS), `/mnt/docker/plex/transcode` (ZFS). **Read-Only**: `/mnt/media/*` (NFS from `tmtdockp04`). |
| **Networks** | `vlan200` (external). Static IP: `192.168.20.4`. |
| **Secrets** | `PLEX_CLAIM` (Env var). Managed via GitOps secrets injection. |
| **Healthcheck** | `curl -f http://127.0.0.1:32400/identity` (30s interval, 3 retries). |

### Configuration shape

Configuration is primarily runtime environment variables (`TZ`, `ADVERTISE_IP`, `NVIDIA_*`). The service initializes a SQLite database within `/config` on first run. `ADVERTISE_IP` must match the static assignment `192.168.20.4` to ensure external discovery works correctly. No external YAML config files are mounted; all tuning occurs via Env vars or the web UI (stored in DB).

## Dependencies

### Hard (service cannot start or operate without these)
- **tmtdockp04** — Provides NFS mounts (`/mnt/media/movies`, etc.). If unreachable, library scans fail, playback returns 404s.
- **tmtdockp03 (Host)** — Provides GPU (A5000) and ZFS storage. Service cannot migrate elsewhere without GPU access.
- **NVIDIA Runtime** — Container requires `runtime: nvidia` enabled on host kernel.

### Soft (degrade if these are down, but service still functional)
- **Internet Access** — Required for metadata fetching, remote access, and `PLEX_CLAIM` verification. Local playback functions without it.

### Reverse (services that depend on THIS service)
- **Client Devices** (TVs, Mobile, Web) — Playback fails immediately.
- **Home Assistant** — Media player entities become `unavailable`.
- **DLNA Controllers** — Discovery broadcast stops.

## State & persistence

- **Database**: SQLite stored at `/config/Library/Application Support/Plex Media Server/`. Contains library DB, user accounts, play history.
- **Filesystem state**:
    - `/config`: Critical. Needs ZFS snapshots. Growth rate ~100MB/year (metadata).
    - `/transcode`: High churn. Temporary files. Should be cleared on restart ideally, but persistent cache exists.
- **In-memory state**: Transcode buffers, active session state. Lost on restart.
- **External state**: None. Media is external (NFS).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 5-10% (idle) | >80% sustained | Throttles playback quality |
| Memory | 1-2GB | >4GB | OOM kills container |
| Disk I/O | 10-50MB/s read (NFS) | >200MB/s write (transcode) | NFS latency spikes |
| Network | 10-100Mbps (streaming) | >1Gbps | Packet loss, buffering |
| GPU | 0% (idle) | >90% utilization | Transcode fails if driver hangs |
| Request latency p50 | <50ms | >500ms | UI hangs |
| Request rate | <50 req/s | >500 req/s | Web UI unresponsive |

## Failure modes

- **NFS Mount Stall**
    - **Symptom**: `ls` hangs inside container, playback freezes.
    - **Root cause**: `tmtdockp04` network partition or NFS server freeze.
    - **Mitigation**: Remount NFS on host (`mount -o remount`). Restart container.
    - **Prevention**: NFS hard mount with timeout tuning (current: unknown).

- **GPU Transcode Hang**
    - **Symptom**: Playback stalls, container healthcheck passes, GPU utilization stuck.
    - **Root cause**: NVIDIA driver state corruption or OOM on GPU memory.
    - **Mitigation**: Restart container.
    - **Prevention**: Monitor GPU temp/memory; limit concurrent transcodes.

- **Claim Token Expiry**
    - **Symptom**: Server unreachable from outside LAN, "Connect to Plex.tv" error.
    - **Root cause**: `PLEX_CLAIM` token expired (valid 4 hours).
    - **Mitigation**: Inject new token env var, restart.
    - **Prevention**: Automate token refresh via GitOps.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Not supported natively for shared state across nodes.
- **Coordination requirements**: None. Single master node.
- **State sharing across replicas**: Impossible without complex DB sync (not supported by Plex). `/config` is strictly single-node.
- **Hardware bindings**: Tightly bound to `tmtdockp03` GPU (A5000). Migration requires identical GPU or disabling hardware acceleration (degraded performance).
- **Network constraints**: Static IP `192.168.20.4` required for DLNA/HomeKit discovery. Multicast traffic must be allowed on `vlan200`.
- **Cluster size constraints**: 1 instance only.
- **Migration cost**: High. Requires moving ZFS datasets and GPU passthrough config. Cannot run active-active.
- **NFS Dependency**: Service cannot be HA if `tmtdockp04` is single-point-of-failure for media storage.

## Operational history

### Recent incidents (last 90 days)
- **None recorded in Corvus**. Last seen `2026-04-11`.

### Recurring drift / chronic issues
- **Image drift**: `latest` tag updates frequently. Occasionally breaks on major version jumps (9.x -> 10.x).
- **Transcode space**: `/transcode` fills up if cleanup fails during crash, causing write errors.

### Known sharp edges
- **NFS vs ZFS**: Do not mount NFS over ZFS without careful tuning.
- **GPU sharing**: A5000 is shared with other workloads. High load on other containers may starve Plex GPU slices.
- **Claim Token**: Hardcoded in env if not managed by secret store; rotates every 4 hours if using standard flow.

## Open questions for Architect

- ? Should we pin the image to a specific digest or major version (e.g., `1.32.0.6834-f57a1a519`) to prevent breaking changes?
- ? What