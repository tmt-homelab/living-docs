

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) — effectively `4` (hardware-bound) due to `pid: host` and kernel module bindings |
| **Tolerable outage** | "hours" — observability loss only; no service degradation downstream |
| **Blast radius if down** | None. Loss of real-time metrics for `tmtdockp04` host and attached containers. No impact on API availability or data integrity. |
| **Recovery time today** | auto-restart (`restart: on-failure`) + manual config sync if ZFS libs mismatch after host upgrade |
| **Owner** | Human: `?` / Agent ID: `claude-code` |

## What this service actually does

Real-time performance monitoring agent for the `tmtdockp04` host. It scrapes kernel stats, Docker container metrics, and ZFS pool health via direct host filesystem and socket access. Exposes a read-only HTTP API on port `19999` for dashboards and alerting.

Other fleet services consume Netdata metrics indirectly via Netdata Cloud (claimed via token) or direct API scraping if configured. It is **NOT** used for long-term historical storage (data retention is short-lived), nor does it execute actions on other services. It is a "dumb" collector bound to the kernel state of the host it runs on.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-security/stacks/monitoring-dockp04/docker-compose.yml` |
| **Image** | `netdata/netdata:latest` |
| **Pinning policy** | Tag-floating (`latest`) — **high risk**. No digest pinning. |
| **Resource caps** | None defined (unbounded CPU/Mem). |
| **Volumes** | **State**: `/mnt/docker/netdata/config`, `/mnt/docker/netdata/cache`, `/mnt/docker/netdata/lib`<br>**Host Bind**: `/proc`, `/sys`, `/var/run/docker.sock`, `/etc/passwd`, `/etc/os-release`<br>**ZFS Libs**: `/usr/sbin/zpool`, `/lib/x86_64-linux-gnu/libzfs.so.4` (specific versions) |
| **Networks** | `infra-services`, `monitoring`, `infra-db`, `homeauto`, `media` (all external) |
| **Secrets** | `NETDATA_CLAIM_TOKEN` (Env var source unknown), `NETDATA_CLAIM_ROOMS` |
| **Healthcheck** | `curl -f http://127.0.0.1:19999/api/v1/info` (30s interval, 10s timeout) |

### Configuration shape

Environment variables control cloud claiming (`NETDATA_CLAIM_TOKEN`, `NETDATA_CLAIM_URL`). Persistent configuration resides in `/mnt/docker/netdata/config` (bind-mounted to `/etc/netdata`). The `docker-compose.yml` injects host paths directly; no external config file is loaded beyond the bind mount.

## Dependencies

### Hard (service cannot start or operate without these)
- **Host Kernel (`/proc`, `/sys`)**: Netdata reads directly from these paths. If host is inaccessible or paths change, Netdata fails to collect system metrics.
- **Docker Daemon (`/var/run/docker.sock`)**: Required to enumerate and monitor container metrics.
- **ZFS Libraries**: Specific shared objects (`libzfs.so.4`, etc.) are bind-mounted. Host OS upgrade breaking these ABI versions breaks ZFS monitoring.

### Soft (degrade if these are down, but service still functional)
- **Netdata Cloud**: Claiming token allows cloud visualization. Without it, local API works but remote dashboards fail.
- **Network egress**: Required for telemetry export to `app.netdata.cloud`.

### Reverse (services that depend on THIS service)
- **None**: No critical service routes traffic through Netdata. It is purely observability.

## State & persistence

- **Database tables / schemas**: SQLite/RRD stored in `/mnt/docker/netdata/lib` and `/mnt/docker/netdata/cache`. Rolling window (default 1hr high-res, days low-res).
- **Filesystem state**: `/mnt/docker/netdata/config` contains `netdata.conf` and plugin configs.
- **In-memory state**: Current metric buffers lost on restart (recovered from disk cache).
- **External state**: Netdata Cloud (if claimed).
- **Backups**: State dirs should be included in host ZFS snapshot policy (`/mnt/docker/netdata`). RPO = snapshot interval.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 2% | > 20% sustained | Spikes during ZFS scrub or container churn |
| Memory | 150MB - 300MB | > 500MB | OOM if host swap thrashing |
| Disk I/O | Low (RRD updates) | High (ZFS sync) | Writes rotate; minimal churn |
| Network | < 10Mbps | > 100Mbps | Bounded by host NIC |
| GPU (if applicable) | N/A | N/A | N/A |
| Request latency p50 / p95 / p99 | < 10ms | > 100ms | Slow if host IO saturated |
| Request rate | Low (polling) | High (dashboards open) | CPU bound by metric collection |

## Failure modes

- **ZFS Lib Mismatch**: Host OS upgrade changes `/lib/x86_64-linux-gnu/libzfs.so` version. Container binds old version → ZFS metrics fail or container crashes.
  - *Mitigation*: Update bind mounts in compose after host upgrade.
- **Privilege Escalation**: `cap_add: SYS_ADMIN` + `apparmor=unconfined` + `docker.sock` mount gives full host root access.
  - *Mitigation*: Network isolation. Do not expose port 19999 externally.
- **Port Conflict**: Port `19999` must be unique per host. Cannot run multiple Netdata instances on same host.
- **Disk Full**: Cache dirs fill up if retention policy misconfigured.
  - *Mitigation*: Monitor