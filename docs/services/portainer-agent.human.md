

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (management plane only) |
| **Blast radius if down** | Portainer Server loses visibility/control of `tmtdockp02`. Workloads continue running unaffected. |
| **Recovery time today** | Auto-restart (unless-stopped) |
| **Owner** | ? |

## What this service actually does

Acts as the remote management bridge between the local Docker daemon on `tmtdockp02` and the central Portainer Server. It proxies API calls for container/stack management and exposes host metrics to the Portainer UI.

The fleet uses it to enable centralized deployment and monitoring of Docker resources across multiple hosts. When it's broken, administrators cannot deploy new stacks or view logs via Portainer on this specific node, but existing containers remain operational.

It is NOT a workload scheduler itself. It does not run user applications; it only reports on the Docker daemon it attaches to.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-security/stacks/monitoring-dockp02/docker-compose.yml` |
| **Image** | `portainer/agent:2.33.7` |
| **Pinning policy** | Tag-fixed (semver `2.33.7`); not digest pinned |
| **Resource caps** | ? (No limits defined in compose) |
| **Volumes** | `/var/run/docker.sock` (ro), `/var/lib/docker/volumes` (ro), `portainer-agent-data` (rw) |
| **Networks** | `ai-gpu2` (external) |
| **Secrets** | `PORTAINER_AGENT_SECRET` (env var, source unknown) |
| **Healthcheck** | None defined in compose |

### Configuration shape

Environment variable driven. Single critical variable `AGENT_SECRET` must match the value registered in the Portainer Server for this endpoint. No configuration files are mounted or expected.

## Dependencies

### Hard (service cannot start or operate without these)
- **Docker Daemon** — Binds to `/var/run/docker.sock`. If daemon is down, agent is useless.
- **Network `ai-gpu2`** — Required for outbound connectivity to Portainer Server.

### Soft (degrade if these are down, but service still functional)
- **Portainer Server** — Agent stays up but cannot sync state or accept commands.

### Reverse (services that depend on THIS service)
- **Portainer Server** — Uses this agent to manage `tmtdockp02`. Loss of agent = orphaned host in UI.

## State & persistence

State is minimal but host-bound.

- **Database tables / schemas**: None (SQLite internal to agent, if any).
- **Filesystem state**: `portainer-agent-data:/data`. Stores agent configuration and temporary state.
  - Growth rate: Negligible.
  - Backup strategy: Docker volume backup required to preserve secret binding.
- **In-memory state**: Connection state to Server. Lost on restart.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | Negligible | ? | ? |
| Network | Low (polling) | ? | ? |
| GPU | None | N/A | N/A |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | Low (heartbeat) | ? | ? |

## Failure modes

- **Secret Mismatch**:
  - **Symptom**: Agent logs show auth errors; Server shows endpoint as "disconnected".
  - **Root cause**: `AGENT_SECRET` env var does not match Server registration.
  - **Mitigation**: Rotate secret on Server, update Env var, restart container.
  - **Prevention**: Enforce secret sync via GitOps pipeline.

- **Socket Permission Denied**:
  - **Symptom**: Agent exits immediately with permission error.
  - **Root cause**: Docker socket permissions changed on host or container lost access.
  - **Mitigation**: Verify socket permissions on `tmtdockp02`.
  - **Prevention**: Immutable infrastructure rebuild.

- **Network Isolation**:
  - **Symptom**: Agent running but Server cannot reach 9001.
  - **Root cause**: Firewall rules or Docker network driver misconfiguration.
  - **Mitigation**: Check `ai-gpu2` network connectivity.
  - **Prevention**: Network policy documentation.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. One agent per Docker host. Running multiple agents on the same socket causes race conditions and duplicate reporting.
- **Coordination requirements**: None. Stateless regarding other agents.
- **State sharing across replicas**: N/A (Single instance per host).
- **Hardware bindings**: Binds to host Docker socket (`/var/run/docker.sock`). Cannot migrate to another host without re-registering with Server.
- **Network constraints**: Port 9001 must be reachable by Portainer Server (usually external to host network or via overlay).
- **Cluster size constraints**: N/A (Distributed host model, not cluster model).
- **Migration cost**: Low. Re-deploy container on new host with matching secret. Server side requires re-adding endpoint.

## Operational history

### Recent incidents (last 90 days)
- ?

### Recurring drift / chronic issues
- ?

### Known sharp edges
- **Version Skew**: Agent version must be compatible with Portainer Server version. Upgrading Server may require Agent update before connection drops.
- **Secret Rotation**: Changing `AGENT_SECRET` requires manual intervention on Server UI unless automated.

## Open questions for Architect

- ? (Source of truth for `PORTAINER_AGENT_SECRET` - 1Password, Vault, or local .env?)
- ? (Is `ai-gpu2` network expected to persist across host reboots reliably?)
- ? (Should healthcheck be added to detect silent agent failures?)

## Reference

- Compose: `homelab-security/stacks/monitoring-dockp02/docker-compose.yml`
- Logs: Docker JSON logs (`/var/lib/docker/containers/<id>/<id>-json.log`)
- Dashboards: Portainer UI > Environments > tmtdockp02
- Runbooks: ?
- Upstream docs: https://docs.portainer.io/
- Related services: `portainer-server` (not in this stack)