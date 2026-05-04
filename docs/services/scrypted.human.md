

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (Non-critical media) |
| **Blast radius if down** | Home Assistant loses camera feeds; Apple HomeKit devices lose video access. No impact on core home automation logic. |
| **Recovery time today** | Auto-restart (Docker `unless-stopped`) + Manual config restore if volume corrupt. |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Scrypted acts as a translation layer and NVR for IP cameras. It ingests RTSP/ONVIF streams, transcodes them for compatibility, and exposes them to HomeKit and Home Assistant. It manages device plugins for various camera brands (Nest, Ring, Reolink, etc.).

Other fleet services consume it via HTTP APIs and WebSockets. Home Assistant pulls camera entities from Scrypted. It is NOT used for archival storage (Plex/Jellyfin) or general media playback; its scope is strictly security camera integration and bridging.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `koush/scrypted:latest` |
| **Pinning policy** | Tag-floating (`latest`). **Risk:** Breaks on upstream major updates. |
| **Resource caps** | ? (None defined in compose) |
| **Volumes** | `/mnt/docker/scrypted:/server/volume` (State), `/var/run/dbus:/var/run/dbus` (Host socket) |
| **Networks** | `proxy`, `homeauto`, `vlan200` (Static: `192.168.20.224`) |
| **Secrets** | ? (Not exposed in compose) |
| **Healthcheck** | `curl -f http://127.0.0.1:11080` (30s interval, 3 retries) |

### Configuration shape

Configuration is primarily stored in the `/server/volume` directory as JSON/SQLite. Environment variables are minimal (`TZ`). Plugins are managed via the web UI at port 11080. Network exposure relies on the `proxy` network for ingress.

## Dependencies

### Hard (service cannot start or operate without these)
- **Network (vlan200)**: Static IP `192.168.20.224` required for camera reachability.
- **Host D-Bus**: `/var/run/dbus` mount required for hardware acceleration or specific plugin functionality.

### Soft (degrade if these are down, but service still functional)
- **None recorded**: CMDB shows empty dependencies.

### Reverse (services that depend on THIS service)
- **Home Assistant**: Consumes camera feeds via Scrypted plugin. Degrades to "unavailable" entities if Scrypted is down.
- **Apple HomeKit**: External clients lose video stream access.

## State & persistence

State is critical for device configuration, plugin settings, and NVR recordings.

- **Database tables / schemas**: SQLite/JSON inside `/server/volume`.
- **Filesystem state**: `/mnt/docker/scrypted` contains all config, cache, and media buffers. Growth rate depends on retention settings (unknown).
- **In-memory state**: Active stream handles, transcode queues. Lost on restart.
- **External state**: ? (No S3 integration visible in compose).

**Backup Strategy**: Unknown. Requires snapshot of `/mnt/docker/scrypted` volume. RPO depends on manual backup cadence.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | > 80% sustained | Transcoding queues back up |
| Memory | ? | > 90% | OOM killer may trigger |
| Disk I/O | ? | ? | ? |
| Network | ? | ? | ? |
| GPU (if applicable) | ? | ? | ? |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Floating Image Tag Update**: `latest` tag pulls new version on restart. New version may drop plugin support.
  - *Symptom:* Web UI returns 500 or plugins fail to load.
  - *Mitigation:* Pin image digest in compose.
- **D-Bus Socket Mismatch**: Host kernel update changes D-Bus behavior.
  - *Symptom:* Hardware accel fails, CPU spikes.
  - *Mitigation:* Restart container, check host permissions.
- **Stream Overload**: Too many cameras configured for local recording.
  - *Symptom:* Container OOM, frequent restarts.
  - *Prevention:* Set memory limits in compose.

## HA constraints (input to fleet-reliability design)

This section dictates the architectural ceiling for reliability improvements.

- **Replicable?** `No`. Scrypted server state is not designed for active-active clustering.
- **Coordination requirements** `None`. Standalone instance.
- **State sharing across replicas** `None`. `/server/volume` cannot be mounted read-write to multiple containers simultaneously.
- **Hardware bindings** `High`. Requires direct host access to `/var/run/dbus`. If GPU passthrough is enabled, it is bound to specific device nodes (not visible in compose but implied by D-Bus).
- **Network constraints** `Medium`. Requires static IP `192.168.20.224` for consistent camera communication.
- **Cluster size constraints** `1`. Active-Active not supported. Active-Passive possible via config sync but not automated.
- **Migration cost** `High`. Moving to replicated state requires external storage sync or manual DB export/import.
- **Port Conflicts**: Internal port 11080. Exposed via `proxy` network (likely 80/443).

## Operational history

### Recent incidents (last 90 days)
- `?` (No incident data available in CMDB)

### Recurring drift / chronic issues
- **Image Drift**: `koush/scrypted:latest` drifts daily/weekly. Requires manual pinning for stability.
- **Volume Growth**: `/mnt/docker/scrypted` grows without rotation checks on cache.

### Known sharp edges
- **D-Bus Permissions**: If host D-Bus policy changes, container may lose hardware accel capability silently.
- **Plugin Updates**: Plugins update independently of core image; version skew can cause API mismatches.

## Open questions for Architect

- Is the `/var/run/dbus` mount strictly required for all deployments, or only for specific hardware accel plugins?
- What is the official backup cadence for `/mnt/docker/scrypted`? Is it covered by `/mnt/docker` general snapshot policy?
- Should we enforce `image: digest` pinning to prevent accidental breaking changes?

## Reference

- **Compose**: `homelab-homeauto/stacks/homeauto/docker-compose.yml`
- **Logs**: `docker logs scrypted` (json-file, 50m max size)
- **Dashboards**: ? (No Grafana integration visible)
- **Runbooks**: ?
- **Upstream docs**: https://github.com/koush/scrypted
- **Related services**: `homeassistant` (consumer), `esphome` (same stack)