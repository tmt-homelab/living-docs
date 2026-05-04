

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | 5-10 minutes (IoT devices buffer or retry) |
| **Blast radius if down** | Home Assistant automation fails, 3x Zigbee2MQTT instances disconnect, ESPHome devices unreachable, Scrypted video events lost |
| **Recovery time today** | Auto-restart (Docker `unless-stopped`); manual config restore if data corruption occurs |
| **Owner** | ? |

## What this service actually does

Acts as the central pub/sub message bus for the TMT Homelab IoT ecosystem. The fleet uses it to decouple hardware state (Zigbee, ESPHome) from logic (Home Assistant). When it's broken, device state updates stop flowing; automations relying on MQTT triggers fail silently or time out.

Primary purpose is reliable message delivery with QoS 1/2 support and retained messages. It is NOT a persistent log store (use Loki/Prometheus for that) and NOT a secure tunnel (TLS must be configured in `config/mosquitto.conf` externally). It functions as the backbone for the `homeauto` network overlay.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `eclipse-mosquitto:latest` |
| **Pinning policy** | `tag-floating` (HIGH RISK — `latest` tag may break auth/config on update) |
| **Resource caps** | None defined (unbounded) |
| **Volumes** | `/mnt/docker/mosquitto/config` (cfg), `/mnt/docker/mosquitto/data` (STATE), `/mnt/docker/mosquitto/log` (logs) |
| **Networks** | `homeauto` (alias: `mosquitto`), `vlan200` (static IP: `192.168.20.223`) |
| **Secrets** | None in Compose (likely plaintext in `config` volume) |
| **Healthcheck** | `mosquitto_sub -t $$SYS/# -C 1 -i healthcheck -W 3` (verifies broker responsiveness) |

### Configuration shape

Configuration is entirely externalized via bind mount at `/mosquitto/config`. Expected files: `mosquitto.conf`, `password.txt`, `acl.txt`. No environment variables injected. The broker listens on 1883 (TCP) and 9001 (WS) exposed to host networks.

## Dependencies

### Hard (service cannot start or operate without these)
- None (self-contained binary + config).
- **Network:** `vlan200` interface must be up for static IP assignment.

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- `homeassistant`: Consumes all device state; automation engine stalls.
- `zigbee2mqtt_up_mbr`: Disconnects from broker; Zigbee devices unmanageable.
- `zigbee2mqtt_dn_kit`: Same as above.
- `zigbee2mqtt_gr_gar`: Same as above.
- `esphome`: Devices connect via IP (`192.168.20.223`) for config logging/status.

## State & persistence

**CRITICAL:** This service holds the source of truth for device retention and session state.

- **Database tables / schemas:** None (uses internal RDB format).
- **Filesystem state:** 
    - `/mnt/docker/mosquitto/data`: Contains `mosquitto.db`. Critical. Growth depends on retained message count (usually MBs, not GBs).
    - `/mnt/docker/mosquitto/log`: Contains `mosquitto.log`. Rotated by Docker JSON driver (`50m` max size).
- **In-memory state:** Active client sessions, QoS 1/2 pending acknowledgments, last-will messages. Lost on restart if not persisted.
- **External state:** None.

**Backup Requirement:** `/mnt/docker/mosquitto/data` must be backed up daily. Restore requires stopping broker, replacing DB, restarting.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% | > 20% sustained | Throttles client connections |
| Memory | 50-100 MB | > 500 MB | OOMKilled by Docker |
| Disk I/O | Low (periodic writes) | High write latency | DB corruption risk |
| Network | Bursty (10-100 msg/s) | > 10k msg/s | Queue backlog grows |
| Request latency p50 / p95 / p99 | < 10ms | > 500ms | Message drops |
| Request rate | Variable | > 5k msg/s | Broker overload |

## Failure modes

- **Disk Full:** Broker stops accepting publishes. 
    - *Symptom:* `Connection refused` or `QoS 1 timeout`.
    - *Root cause:* Log volume fills up (if not rotated) or system root fills.
    - *Mitigation:* Clear logs, restart.
- **Config Drift:** Manual edits to `config` volume outside GitOps.
    - *Symptom:* Broker won't start after restart.
    - *Root cause:* Syntax error in `mosquitto.conf`.
    - *Mitigation:* Restore from GitOps config.
- **Floating Tag Update:** `latest` tag pulls new version.
    - *Symptom:* Auth failures, config incompatibility (e.g., password hash changes).
    - *Root cause:* Image digest changed without config migration.
    - *Mitigation:* Pin image digest.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (native clustering unsupported in standard image).
- **Coordination requirements:** None (single node).
- **State sharing across replicas:** Impossible. `mosquitto.db` is file-locked; cannot be mounted to multiple nodes simultaneously.
- **Hardware bindings:** None (software only).
- **Network constraints:** Ports 1883 and 9001 must be unique per host if attempting manual HA. Requires VIP or DNS split-horizon for failover.
- **Cluster size constraints:** Not applicable.
- **Migration cost:** High. To move to HA, must implement Redis backend or use clustering plugins, requiring config rewrite and data migration. Current design assumes single-point-of-failure for this component.

## Operational history

### Recent incidents (last 90 days)
- None recorded in Corvus.

### Recurring drift / chronic issues
- `latest` tag drift: Unexpected version upgrades during pull.
- Auth config changes: Passwords often stored in plain text or weak hashes in `config` volume.

### Known sharp edges
- **TLS:** If TLS is enabled in `config`, client certificates must be distributed to all Zigbee2MQTT instances.
- **ACL:** Overly permissive ACLs allow Zigbee devices to publish to Home Assistant topics they shouldn't touch.
- **QoS:** Default QoS 0 means "at most once". Critical state should force QoS 1 in client config.

## Open questions for Architect

- ? Why is image tag `latest` instead of pinned digest? (Security/Stability risk)
- ? Is TLS mutually authenticated between Zigbee2MQTT and Mosquitto?
- ? What is the RPO for `/mnt/docker/mosquitto/data`? (Currently undefined)
- ? Can we move to a managed MQTT broker (e.g., EMQX) for better HA support?

## Reference

- Compose: `homelab-homeauto/stacks/homeauto/docker-compose.yml`
- Logs: `/mnt/docker/mosquitto/log/mosquitto.log` + Docker JSON
- Dashboards: N/A (Prometheus exporter not configured)
- Runbooks: N/A
- Upstream docs: https://mosquitto.org/documentation/
- Related services: `homeassistant`, `zigbee2mqtt_up_mbr`, `zigbee2mqtt_dn_kit`, `zigbee2mqtt_gr_gar`