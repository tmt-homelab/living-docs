

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope) |
| **Tolerable outage** | 1 hour (garage automation delays acceptable) |
| **Blast radius if down** | Garage devices (lights, sensors) stop reporting state; Home Assistant automation for zone `gar` fails |
| **Recovery time today** | Auto-restart (Docker `unless-stopped`); manual USB re-bind if adapter drops |
| **Owner** | `tmt_todd` (inferred from Git repo), provisioned by `claude-code` |

## What this service actually does

Zigbee2MQTT bridges local Zigbee wireless devices to the fleet MQTT broker. It translates raw Zigbee mesh traffic into JSON payloads consumed by Home Assistant. This instance (`gr_gar`) is scoped specifically to the Garage zone hardware.

Other fleet services consume its output via MQTT topics (`zigbee2mqtt/...`). It is NOT a general IoT bridge for Wi-Fi or Z-Wave devices. It is one of three peer gateways (`up_mbr`, `dn_kit`) running the same image but managing disjoint device sets.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-homeauto/stacks/homeauto/docker-compose.yml` |
| **Image** | `koenkk/zigbee2mqtt:latest` |
| **Pinning policy** | Tag-floating (`latest`); risky for production stability |
| **Resource caps** | None defined |
| **Volumes** | `/mnt/docker/zigbee2mqtt_gr_gar:/app/data` (Stateful) |
| **Networks** | `homeauto` (internal), `vlan200` (192.168.20.198) |
| **Secrets** | None in compose; credentials likely in `/app/data/configuration.yaml` |
| **Healthcheck** | `wget -q --spider http://127.0.0.1:8080` (30s interval, 3 retries) |

### Configuration shape

Configuration resides in the bind-mounted volume at `/app/data`. Primary artifact is `configuration.yaml`. Environment variable `TZ=America/Los_Angeles` is passed. Service connects to MQTT broker at `mosquitto:1883` (network alias).

## Dependencies

### Hard (service cannot start or operate without these)
- **mqtt** — Eclipse Mosquitto broker. Without this, device state cannot be published; container starts but logs connection refused errors.

### Soft (degrade if these are down, but service still functional)
- **N/A** — Service functions independently of HTTP proxies or databases.

### Reverse (services that depend on THIS service)
- **homeassistant** — Consumes MQTT topics. HA loses garage sensor updates if this service is down.
- **zigbee2mqtt_up_mbr / dn_kit** — Peer gateways. Independent operation, but share the same MQTT broker namespace.

## State & persistence

- **Database tables / schemas:** SQLite `database.db` inside volume (device metadata, network map).
- **Filesystem state:** `/mnt/docker/zigbee2mqtt_gr_gar` contains `configuration.yaml`, `database.db`, `log.txt`.
- **In-memory state:** Zigbee coordinator cache (rebuilt from DB on restart).
- **External state:** None. All state is local to the host volume.
- **Backup:** Depends on host-level backup of `/mnt/docker`. No internal replication.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 50% | N/A |
| Memory | ~150MB | > 512MB | GC pressure |
| Disk I/O | Low | N/A | Log growth |
| Network | Bursty | N/A | MQTT QoS backlog |
| GPU | None | N/A | N/A |
| Request latency p50 / p95 / p99 | < 100ms | > 2s | Message queue depth |
| Request rate | Variable (sensor events) | N/A | MQTT broker limit |

## Failure modes

- **Symptom:** Healthcheck fails (HTTP 8080 unreachable). **Root cause:** Node.js process hang or Zigbee coordinator disconnect. **Mitigation:** `docker restart`. **Prevention:** Watchdog script for USB device presence.
- **Symptom:** Devices go offline in HA. **Root cause:** MQTT broker auth change or network partition. **Mitigation:** Verify `mosquitto` connectivity. **Prevention:** Secret rotation policy.
- **Symptom:** Logs fill disk. **Root cause:** Verbose logging enabled. **Mitigation:** `log_level: info` in config. **Prevention:** Log rotation (50m max-size configured).

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Bound to specific USB Zigbee coordinator hardware.
- **Coordination requirements:** None. Federated gateway pattern (independent nodes).
- **State sharing across replicas:** None. Each instance manages its own device list.
- **Hardware bindings:** Requires USB passthrough (not visible in compose, implied by service type). If container moves host, USB adapter must be re-mapped.
- **Network constraints:** Static IPv4 `192.168.20.198` on `vlan200`. Unique IP required per gateway instance to avoid ARP conflicts if running on same host (currently separate IPs).
- **Cluster size constraints:** N/A.
- **Migration cost:** High. Moving service requires moving physical USB adapter + volume data. Re-pairing devices required if volume lost.

## Operational history

### Recent incidents (last 90 days)
- `?` (No incident data in CMDB)

### Recurring drift / chronic issues
- `?` (No historical data)

### Known sharp edges
- **Tag floating:** `latest` tag can introduce breaking changes without notice. Recommend digest pinning.
- **USB persistence:** Docker device mapping (`/dev/ttyUSB*`) can change on reboot. Requires `udev` rules for stable device ID.

## Open questions for Architect

- How is the USB Zigbee adapter mapped to the container (device list not shown in compose)?
- Is `/mnt/docker` on a ZFS pool with snapshots for volume recovery?
- Should `latest` tag be replaced with a specific digest for fleet stability?

## Reference

- **Compose:** `homelab-homeauto/stacks/homeauto/docker-compose.yml`
- **Logs:** `json-file` driver, max 50m per file, 3 files retained.
- **Dashboards:** ?
- **Runbooks:** ?
- **Upstream docs:** https://www.zigbee2mqtt.io/
- **Related services:** `zigbee2mqtt_up_mbr`, `zigbee2mqtt_dn_kit`, `mqtt`