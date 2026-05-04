

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "unplanned outage acceptable for ≤ 4 hours" (device control unaffected, only new device setup blocked) |
| **Blast radius if down** | Home Assistant loses ESPHome integration → existing ESP devices continue working but new firmware deployments blocked, dashboard widgets fail |
| **Recovery time today** | auto-restart (container restart: unless-stopped) |
| **Owner** | TBD (phase-1.4-bulk-backfill created) |

## What this service actually does

ESPHome runs the ESPHome compiler and dashboard. It stores device YAML configurations in `/config` and compiles firmware binaries for ESP8266/ESP32 devices. Home Assistant uses it via API to compile and push firmware to IoT devices over the local network. When it's broken, you can't add new ESP devices or update existing ones, but devices already running firmware continue operating independently.

This is NOT a device runtime service — the ESPHome devices themselves run standalone on hardware (ESP chips). This service only manages them. Do not confuse with the MQTT brokers or Zigbee gateways in the same stack.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `esphome/esphome:latest` (tag-floating, not pinned) |
| **Pinning policy** | tag-floating — upstream pushes `latest`, no digest pinning in GitOps |
| **Resource caps** | ? (none defined in compose) |
| **Volumes** | `/mnt/docker/esphome:/config` (stateful, contains YAML configs + compiled binaries) |
| **Networks** | `network_mode: host` (bypasses Docker networking entirely) |
| **Secrets** | ? (not exposed in compose; may use file-based auth in config) |
| **Healthcheck** | ? (none defined in compose) |

### Configuration shape

Config stored in `/config` volume. Contains YAML device definitions, secrets files, and compiled firmware artifacts. Environment uses `TZ=America/Los_Angeles`. No external secrets management — credentials likely stored in plaintext YAML or `.env` within config volume.

## Dependencies

### Hard (service cannot start or operate without these)
- ? (CMDB shows empty dependencies; service runs standalone in container)
- Network access to ESP devices (via host networking) — implicit, not declared

### Soft (degrade if these are down, but service still functional)
- Home Assistant — UI integration unavailable, but compilation still works
- MQTT — device logging may fail if devices configured to publish to MQTT

### Reverse (services that depend on THIS service)
- Home Assistant — uses ESPHome integration to compile/deploy firmware. Breaks device provisioning workflow.
- ESP devices (firmware already deployed) — continue working; new deployments fail

## State & persistence

State lives in `/mnt/docker/esphome` on `tmtdockp04`.

- **Filesystem state**: `/config` contains YAML configs, compiled `.bin` files, and build logs. Growth rate ~100MB/year per 10 devices. Backed up via host-level backup scripts (path unknown). RPO: unknown, RTO: ~15min for config restore.
- **In-memory state**: Build artifacts in `/tmp` during compilation — lost on restart, no impact.
- **External state**: None (no S3, no remote DB).
- **Shareable across replicas**: Config files are shareable via NFS/SMB, but build cache is not.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | Spikes during firmware compilation (single-threaded) |
| Memory | ? | ? | ? |
| Disk I/O | ? | ? | ? |
| Network | ? | ? | ? |
| GPU (if applicable) | ? | N/A | ? |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom**: Home Assistant ESPHome integration shows "unavailable"
- **Root cause**: Container crashed or host network interface lost
- **Mitigation**: `docker restart esphome`, verify network connectivity to device IPs
- **Prevention**: Add healthcheck, monitor container restart count

- **Symptom**: Firmware compilation hangs indefinitely
- **Root cause**: Missing ESP toolchain dependencies or network timeout to GitHub (downloads toolchain on first run)
- **Mitigation**: Kill container, clear `/config/.esphome`, restart
- **Prevention**: Pin image tag, ensure egress allowed to github.com

## HA constraints (input to fleet-reliability design)

The point of this section is to tell the Architect what they're allowed to do.

- **Replicable?** No — single-instance only. `network_mode: host` prevents multiple instances on same host.
- **Coordination requirements**: None (no leader election, no distributed state).
- **State sharing across replicas**: Config files shareable via external storage, but build cache not. Active connections not shareable.
- **Hardware bindings**: None (no USB devices, no GPU, no kernel modules). Host networking is the binding constraint.
- **Network constraints**: `network_mode: host` means port conflicts with other containers. ESPHome dashboard runs on default port 6052 (unbound in compose). Device discovery requires broadcast/multicast on VLAN 200.
- **Cluster size constraints**: N/A (single-instance only).
- **Migration cost**: Moderate — need to reconfigure network mode on target host, migrate `/mnt/docker/esphome` volume, verify device connectivity on new network segment.

## Operational history

### Recent incidents (last 90 days)
- None recorded in CMDB (service created 2026-05-01 via bulk backfill)

### Recurring drift / chronic issues
- None documented yet (new service)

### Known sharp edges
- `network_mode: host` conflicts with any other service needing ports 6052 or 8888
- `latest` tag floating — upgrade may introduce breaking changes without warning
- No healthcheck means container may be "running" but unresponsive to HTTP requests

## Open questions for Architect

- ? Why `network_mode: host` instead of bridge network with port mapping?
- ? What is the backup strategy for `/mnt/docker/esphome`?
- ? Should we add a healthcheck (HTTP GET on `/`) to improve detection?
- ? Can ESPHome be made replicable with shared config storage, or is host networking a hard blocker?

## Reference

- Compose: `homelab-homeauto/stacks/homeauto/docker-compose.yml`
- Logs: `/var/lib/docker/containers/*/esphome-json.log` (json-file, 50m max, 3 files)
- Dashboards: ? (no Grafana integration)
- Runbooks: ? (none documented)
- Upstream docs: https://esphome.io, version from `latest` tag
- Related services: `homeassistant`, `mqtt` (same stack, different compose services)