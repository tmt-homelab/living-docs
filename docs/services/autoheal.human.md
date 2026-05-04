

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless utility) |
| **Tolerable outage** | Hours (service degrades resilience, does not break core functionality) |
| **Blast radius if down** | Unhealthy containers remain down until manual intervention or restart. No data loss. |
| **Recovery time today** | Automatic (Docker `on-failure` restart policy) |
| **Owner** | ? |

## What this service actually does

Monitors the Docker daemon on `tmtdockp04` and restarts containers that fail health checks or become unhealthy. It operates as a passive observer and corrective agent. It polls container status based on label filters (`AUTOHEAL_CONTAINER_LABEL=all`) every 60 seconds.

Other fleet services do not call this service directly. It operates out-of-band via the Docker socket. It is NOT a logging aggregator, NOT a metrics collector, and NOT a general monitoring dashboard. It does not send alerts when it restarts a container; it only acts.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/dockp04-core/docker-compose.yml` |
| **Image** | `willfarrell/autoheal:latest` |
| **Pinning policy** | Tag-floating (`latest`) — risky, no digest pinning observed |
| **Resource caps** | None defined |
| **Volumes** | `/var/run/docker.sock:/var/run/docker.sock:ro` (Critical binding) |
| **Networks** | Default bridge (not attached to `infra-services`, `monitoring`, etc.) |
| **Secrets** | None (relies on host socket permissions) |
| **Healthcheck** | None defined in compose |

### Configuration shape

Configuration is purely environment variable driven. No config files mounted.
- `AUTOHEAL_CONTAINER_LABEL`: Filter key (set to `all`).
- `AUTOHEAL_INTERVAL`: Polling frequency (60s).
- `AUTOHEAL_START_PERIOD`: Grace period before checking (300s).

## Dependencies

### Hard (service cannot start or operate without these)
- **Docker Daemon** — Required for socket access (`/var/run/docker.sock`). If Docker is down, autoheal cannot function.
- **Host Network** — Requires access to host filesystem for socket mount.

### Soft (degrade if these are down, but service still functional)
- **None** — Service is self-contained.

### Reverse (services that depend on THIS service)
- **All labeled containers** — Any container with label `all` depends on this for automatic recovery. If this is down, recovery is manual.

## State & persistence

No persistent state is maintained by the service.
- **Database tables**: None.
- **Filesystem state**: None. Logs are ephemeral (`json-file`, 50m max).
- **In-memory state**: Container status cache (lost on restart).
- **External state**: None.
- **Backups**: Not applicable.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | <1% (polling) | >10%