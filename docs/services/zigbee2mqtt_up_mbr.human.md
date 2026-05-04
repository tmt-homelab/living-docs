

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for container-level HA) |
| **Tolerable outage** | 2-4 hours (local zone control loss, no safety impact) |
| **Blast radius if down** | `homeassistant` loses visibility/control for devices in "Upper Master Bedroom" zone. MQTT topics for `zigbee2mqtt_up_mbr/#` stop updating. |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual intervention if USB stick fails or config corrupts |
| **Owner** | `claude-code` (Agent); Human: `?` |

## What this service actually does

Bridges Zigbee radio traffic from a specific USB coordinator to the MQTT bus. This instance (`up_mbr`) handles devices physically located in the upper master bedroom zone. It does not manage network routing or general IoT traffic.

Consumers (primarily `homeassistant`) subscribe to MQTT topics published by this service to render device states. It is NOT a hub for all Zigbee devices; other instances (`zigbee2mqtt_dn_kit`, `zigbee2mqtt_gr_gar`) handle other zones. Do not treat this as a fleet-wide single point of truth for Zigbee.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `koenkk/zigbee2mqtt:latest` |
| **Pinning policy** | `tag-floating` (Latest) — High risk for breaking changes on pull |
| **Resource caps** | None defined (defaults) |
| **Volumes** | `/mnt/docker/zigbee2mqtt_up_mbr` → `/app/data` (State: Config, DB, Logs) |
| **Networks** | `homeauto` (internal), `vlan200` (192.168.20.196) |
| **Secrets** | None in compose (MQTT creds likely in `configuration.yaml` inside volume) |
| **Healthcheck** | `wget -q --spider http://127.0.0.1:8080` (Internal Web UI/API) |

### Configuration shape

Configuration resides in `/app/data/configuration.yaml` within the container (host: `/mnt/docker/zigbee2mqtt_up_mbr`). Contains MQTT broker address, network settings, and device permit-join state. Environment variable `TZ` is set to `America/Los_Angeles`.

## Dependencies

### Hard (service cannot start or operate without these)
- **mqtt** — Broker connection required for startup. If `mosquitto` is unreachable, Z2M exits or loops on reconnect.
- **USB Serial Device** — *Critical Gap*: Compose lacks `devices:` mapping. Functionally required for Zigbee adapter (e.g., `/dev/ttyACM0`).

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **homeassistant** — Consumes MQTT topics (`zigbee2mqtt/up_mbr/#`). Breakage results in "Unavailable" states for specific devices in HA UI.
- **zigbee2mqtt_dn_kit / gr_gar** — Independent coordinators. No direct dependency, but share MQTT broker resources.

## State & persistence

State is entirely filesystem-based within the mounted volume.

- **Database:** `/app/data/database.db` (SQLite). Contains device network keys, IEEE addresses, and group mappings.
- **Config:** `/app/data/configuration.yaml`. Persistent settings.
- **Logs:** `/app/data/log/`. Rotated by JSON-file driver (50m max).
- **Growth rate:** Slow (KB/day). Device join events spike usage.
- **Backup:** Depends on `/mnt/docker` volume backup strategy (unspecified in inputs).
- **Replication:** None. State is unique to the specific USB coordinator hardware.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 50% | N/A |
| Memory | 100-300MB | > 500MB | OOM Kill |
| Disk I/O | Low (mostly reads) | High Write | N/A |
| Network | Bursty (MQTT pub/sub) | > 10MB/s | MQTT Buffer overflow |
| Request latency p50 | < 50ms (HTTP 8080) | > 1s | UI timeout |
| Request rate | Low (polling) | High (flash flood) | Broker queue fill |

## Failure modes

- **Symptom:** Devices show "Unavailable" in Home Assistant.
  **Root cause:** `mqtt` broker unreachable or Z2M lost connection.
  **Mitigation:** Check `mqtt` service status. Restart Z2M container.
  **Prevention:** Add alert on `zigbee2mqtt_up_mbr` healthcheck failure.

- **Symptom:** Container restarts loop.
  **Root cause:** `configuration.yaml` syntax error or USB device missing.
  **Mitigation:** Inspect logs (`docker logs zigbee2mqtt_up_mbr`).
  **Prevention:** GitOps validation before deploy.

- **Symptom:** Web UI (8080) inaccessible externally.
  **Root cause:** Port not exposed in compose (intentional).
  **Mitigation:** Use `docker exec` or SSH to host.
  **Prevention:** N/A (Security design).

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Each instance binds to a unique physical Zigbee coordinator.
- **Coordination requirements:** None. Instances are siloed by hardware and config.
- **State sharing across replicas:** None. `database.db` is unique per instance.
- **Hardware bindings:** **CRITICAL.** Requires USB Serial Passthrough (e.g., `/dev/serial/by-id/...`).