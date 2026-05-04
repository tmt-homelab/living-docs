

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | `unplanned outage acceptable for ≤ 1 hour` |
| **Blast radius if down** | `Zigbee devices in 'dn_kit' zone (Downstairs Kitchen) lose telemetry & control. Home Assistant loses visibility for specific entities.` |
| **Recovery time today** | `auto-restart` (if container dies), `manual` (if USB hardware disconnects or config corrupts) |
| **Owner** | `claude-code` (via Corvus registration) |

## What this service actually does

Translates Zigbee RF traffic into MQTT messages for the `mqtt` broker. This specific instance (`dn_kit`) is bound to a physical Zigbee coordinator located in the Downstairs Kitchen area. It exposes device state (battery, temp, switch status) to `homeassistant` via MQTT topics.

The fleet uses it as a peripheral gateway for IoT devices. When it's broken, `homeassistant` stops receiving updates for devices paired to this specific coordinator. It is NOT used for firmware flashing (though it can trigger OTA) or for managing the other Zigbee coordinators (`up_mbr`, `gr_gar`), which run as separate isolated instances.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `koenkk/zigbee2mqtt:latest` |
| **Pinning policy** | `tag-floating` (`latest`). Risk: Updates may introduce breaking changes in `configuration.yaml` or device support. |
| **Resource caps** | `?` (Not defined in compose) |
| **Volumes** | `/mnt/docker/zigbee2mqtt_dn_kit:/app/data` (State: config + DB) |
| **Networks** | `homeauto`, `vlan200` (Static IP: `192.168.20.197`) |
| **Secrets** | `?` (Credentials stored in volume config, not env vars) |
| **Healthcheck** | `wget -q --spider http://127.0.0.1:8080` (HTTP 200/401 expected). Interval 30s, Start period 60s. |

### Configuration shape

Configuration is managed via `/app/data/configuration.yaml` inside the container (mounted at `/mnt/docker/zigbee2mqtt_dn_kit`).
- **Top level:** `mqtt`, `serial`, `homeassistant`, `permit_join`, `advanced`.
- **Env vars:** Only `TZ` is passed explicitly.
- **Secrets:** MQTT password likely embedded in `configuration.yaml` on disk.

## Dependencies

### Hard (service cannot start or operate without these)
- `mqtt` — Broker endpoint (`192.168.20.223`). If down, Zigbee2MQTT cannot publish device updates or receive commands.
- USB Serial Adapter — Physical hardware required for RF communication (binding not explicitly visible in compose snippet).

### Soft (degrade if these are down, but service still functional)
- `homeassistant` — Service can run and log to MQTT, but UI visibility is lost.

### Reverse (services that depend on THIS service)
- `homeassistant` — Consumes MQTT topics for device automation. Breaks automation logic dependent on kitchen sensors.

## State & persistence

- **Filesystem state:** `/mnt/docker/zigbee2mqtt_dn_kit`.
    - `configuration.yaml`: Static config (MQTT creds, ports).
    - `database.db`: SQLite DB of paired devices, group memberships, mappings. **Critical for recovery.**
    - `log.txt`: Debug/Info logs.
    - Growth rate: Slow (KB/day mostly).
- **In-memory state:** Active Zigbee network topology, temporary message queues. Lost on restart (recovered from DB).
- **External state:** None.
- **Backup:** Requires periodic backup of `/mnt/docker/zigbee2mqtt_dn_kit`. No automated snapshot policy visible in inputs.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | `< 2%` | `> 50%` sustained | N/A |
| Memory | `150-250MB` | `> 512MB` | OOM Kill |
| Disk I/O | `Low` (SQLite writes) | `> 10MB/s` | Slow device join |
| Network | `Low` (Event bursts) | `> 100KB/s` | MQTT backlog |
| Request latency p50 | `?` | `?` | `?` |
| Request rate | `Event-driven` | `?` | `?` |

## Failure modes

- **USB Device Disconnect:**
    - **Symptom:** Healthcheck fails, logs show `Serial port not found` or `Failed to connect to serial port`.
    - **Root cause:** Dongle unseated, USB power failure, or host kernel driver crash.
    - **Mitigation:** Re-seat dongle, restart container.
