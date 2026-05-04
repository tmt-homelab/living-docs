

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for standard HA) |
| **Tolerable outage** | Hours (non-critical monitoring service) |
| **Blast radius if down** | Local bird detection stops. No downstream service degradation. |
| **Recovery time today** | Auto-restart (`unless-stopped`) if host is up. |
| **Owner** | ? |

## What this service actually does

Runs audio inference to identify bird species from connected sound cards. Consumes raw audio streams from `/dev/snd`, processes them through ML models, and stores detection events in a local database. Exposes a web UI on port 8080 for manual analysis and configuration.

The fleet uses it for environmental monitoring on `tmtdockp04`. It is NOT used for security surveillance, voice command processing, or general audio recording. It does not expose audio streams to other services; it is a sink for audio input and a source for detection metadata.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/misc/docker-compose.yml` |
| **Image** | `ghcr.io/tphakala/birdnet-go:latest` |
| **Pinning policy** | Tag-floating (`latest`). Risk of breaking changes on pull. |
| **Resource caps** | ? (No CPU/mem limits defined in compose) |
| **Volumes** | `/mnt/docker/birdnet-go/data` (State/DB), `/mnt/docker/birdnet-go/config` (Settings) |
| **Networks** | `homeauto`, `vlan200` (Static: `192.168.20.54`) |
| **Secrets** | None (No 1Password mounts visible) |
| **Healthcheck** | `wget -qO /dev/null http://127.0.0.1:8080/` (Interval: 30s, Retries: 3) |

### Configuration shape

Environment variables are minimal (`TZ`). Primary config lives in `/root/.config/birdnet-go` mounted volume. Expected top-level keys: `AudioInput`, `Database`, `ModelPath`. No external secret management observed.

## Dependencies

### Hard (service cannot start or operate without these)
- **Audio Hardware** — `/dev/snd` must be present and accessible. Service fails to process audio if missing.
- **Host OS** — `tmtdockp04` kernel must support ALSA/PulseAudio passthrough.

### Soft (degrade if these are down, but service still functional)
- **Network** — Web UI inaccessible, but local audio processing continues.

### Reverse (services that depend on THIS service)
- None recorded in CMDB.

## State & persistence

State is local to the host and non-replicable.

- **Database tables / schemas**: SQLite likely within `/mnt/docker/birdnet-go/data`. Contains detection logs, confidence scores, timestamps.
- **Filesystem state**: `/mnt/docker/birdnet-go/data` (Models + DB), `/mnt/docker/birdnet-go/config` (User prefs). Growth rate depends on detection frequency.
- **In-memory state**: Model weights loaded at startup. Lost on restart (reloads from disk).
- **External state**: None. No S3/Sync observed.

**Backup Policy**: Host-level backup of `/mnt/docker/birdnet-go` required. Application-level backup unknown.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | Spikes during inference batches |
| Memory | ? | ? | ? |
| Disk I/O | Low (logs) | High (DB writes) | ? |
| Network | Low (UI polling) | ? | ? |
| GPU (if applicable) | ? | ? | ? |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom**: Healthcheck fails. **Root cause**: Audio device unmapped or permission denied. **Mitigation**: Re-bind `/dev/snd`. **Prevention**: Host boot script validation.
- **Symptom**: UI 500 errors. **Root cause**: SQLite DB locked/corrupted. **Mitigation**: Restart container. **Prevention**: Check disk space.
- **Symptom**: No detections. **Root cause**: Model files missing or corrupted in `/data`. **Mitigation**: Restore from backup. **Prevention**: Verify image integrity on upgrade.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Requires exclusive access to host audio hardware (`/dev/snd`).
- **Coordination requirements**: None. Single instance only.
- **State sharing across replicas**: Not applicable (single instance). State cannot be shared across nodes due to hardware binding.
- **Hardware bindings**: `/dev/snd` (ALSA device). Cannot move to headless nodes.
- **Network constraints**: Static IPv4 `192.168.20.54` on `vlan200`. Port 8080 internal.
- **Cluster size constraints**: 1 node max per audio interface.
- **Migration cost**: High. Requires physical audio device transfer or reconfiguration of virtual audio passthrough on target host.
- **State portability**: `/data` and `/config` volumes are portable, but useless without compatible audio hardware.

## Operational history

### Recent incidents (last 90 days)
- ?

### Recurring drift / chronic issues
- ? (Bulk backfill registration suggests automated onboarding without manual review).

### Known sharp edges
- Tag `latest` may introduce breaking API changes in UI or config format without warning.
- `/dev/snd` binding relies on host kernel stability; USB audio dongles may fail after host reboot if udev rules drift.

## Open questions for Architect

- ? What is the RPO for `/mnt/docker/birdnet-go` data?
- ? Is there a preferred image digest for `ghcr.io/tphakala/birdnet-go` to enable pinning?
- ? Should `vlan200` exposure be restricted to specific subnets via firewall rules?

## Reference

- **Compose**: `homelab-core/stacks/misc/docker-compose.yml`
- **Logs**: Docker daemon (`/var/lib/docker/containers/...`), driver `json-file`, max 150MB retention.
- **Dashboards**: ?
- **Runbooks**: ?
- **Upstream docs**: https://github.com/tphakala/birdnet-go
- **Related services**: ?