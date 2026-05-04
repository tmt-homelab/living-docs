

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes to 1 hour (security automations, HVAC, lighting halts) |
| **Blast radius if down** | Central orchestration lost. `zigbee2mqtt_*`, `scrypted`, and `esphome` lose state aggregation and automation triggers. UI/API offline. Local device control degrades to fallback/static states. |
| **Recovery time today** | Manual or scripted `docker compose restart homeassistant` (~2-4 min including DB reconnect and integration polling) |
| **Owner** | `?` (CMDB registered by `claude-code`) |

## What this service actually does

`homeassistant` acts as the central control plane for the homelab automation fleet. It ingests telemetry and device state from `mqtt`, `zigbee2mqtt_*`, `esphome`, and `scrypted` over HTTP/MQTT. It executes YAML/template automations, maintains a device/entity registry, and serves a REST/WebSocket API at `:8123`.

The fleet consumes it via its API for dashboard rendering, script execution, and state polling. It is **NOT** the event broker (that's `mqtt`/Mosquitto) or the primary data store (recorder offloads to `homeassistant-postgres`). It is a stateful orchestration hub that expects a 1:1 instance-to-environment mapping.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `ghcr.io/home-assistant/home-assistant:stable` |
| **Pinning policy** | `stable` tag floating; no digest pinning in compose. Relying on upstream CI to keep `stable` backward-compatible. |
| **Resource caps** | `?` (unconstrained in compose; no CPU/mem limits set) |
| **Volumes** | `./configs:/config` (application state, secrets, storage), `/run/dbus:/run/dbus:ro` (host system bus) |
| **Networks** | `proxy`, `homeauto`, `db-ha`, `egress`, `vlan200` (fixed `192.168.20.222`) |
| **Secrets** | `?` (no 1Password/SecretsManager mount shown; relies on env/default) |
| **Healthcheck** | Defined. `curl` to `127.0.0.1:8123/api/` expecting `200` or `401`. 30s interval, 10s timeout, 5 retries, 180s start_period. |

### Configuration shape
Top-level `configuration.yaml` defines automations, scripts, integrations, and recorder settings. State lives in `/config/storage/` and `/config/.storage/` (JSON blobs). Env vars are minimal (`TZ=America/Los_Angeles`). Integrations are loaded dynamically at boot or via UI, writing back to `/config`.

## Dependencies

### Hard (service cannot start or operate without these)
- `homeassistant-postgres` — Recorder backend. Fallback to SQLite occurs if unreachable, but degrades performance and breaks long-term statistics.
- `mqtt` — Core event/state bus. Missing broker breaks entity polling, command dispatch, and internal component communication.

### Soft (degrade if these are down, but service still functional)
- `zigbee2mqtt_*` — Device adapters for upper master bedroom, downstairs kitchen, garage. State becomes stale; automations relying on triggers fail.
- `scrypted` — Camera/NVR integration. Media streams and camera entities go unavailable.
- `esphome` — Custom ESP32 firmware control plane. Devices remain online but lose configuration updates and HA API polling.

### Reverse (services that depend on THIS service)
- `zigbee2mqtt_*`, `scrypted`, `esphome`