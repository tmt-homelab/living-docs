

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless compute) / `3` (single-instance stateful volume) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 4 hours (batch blog generation) |
| **Blast radius if down** | Blog pipeline flows stuck in `Scheduled`/`Running`. No impact on infra automation, HA, or core control plane. |
| **Recovery time today** | Auto-restart (`on-failure:5`). Run rescheduling handled by `prefect-server` Foreman service (30s heartbeat). |
| **Owner** | tmiller (Human) / `prefect-ops-agent` (Agent) |

## What this service actually does

Executes Prefect flows registered to the `blog-pipeline-pool`. Isolates blog content generation from the `default-pool` (infrastructure automation) to limit lateral movement blast radius if the blog API key is compromised.

- **Primary purpose**: Renders blog drafts from markdown sources, runs AI classification via LiteLLM, publishes via Admin API.
- **Consumption**: Polls `prefect-server` (192.168.20.18:4200) for task assignments.
- **Output**: Writes generated artifacts to `/mnt/docker/blog-drafts` on host `tmtdockp04`.
- **NOT used for**: Infrastructure provisioning, HA device control, or database migrations (those run on `prefect-worker` default-pool).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `prefect-worker:latest` (local build from `Dockerfile.worker`) |
| **Pinning policy** | Tag-floating (`latest`). **Risk**: Deploys can pull unexpected base changes if rebuild triggered. |
| **Resource caps** | `cpus: "1.0"`, `memory: 1g` |
| **Volumes** | `/mnt/docker/blog-drafts:/app/drafts` (stateful output), `tmpfs: /tmp`, `tmpfs: /home/prefect/.prefect` |
| **Networks** | `automation`, `infra-services` (excluded from `homeauto` bridge for security) |
| **Secrets** | `ADMIN_API_TOKEN`, `LITELLM_MASTER_KEY`, `SLACK_WEBHOOK_URL_BLOG` (injected via 1Password Connect) |
| **Healthcheck** | `python3 -c "import os; os._exit(0 if b'prefect' in open('/proc/1/cmdline','rb').read() else 1)"` (30s interval) |

### Configuration shape

Environment variables passed via compose `.env` (resolved by 1Password Connect).
- **API Endpoint**: `PREFECT_API_URL` (hardcoded to `http://prefect-server:4200/api`).
- **External APIs**: `LITELLM_URL` (192.168.20.15), `ADMIN_API_URL` (localhost:8000).
- **Paths**: `BLOG_DRAFTS_DIR` set to `/app/drafts`.
- **Security**: Read-only rootfs enforced; writable areas restricted to `tmpfs` and mounted volume.

## Dependencies

### Hard (service cannot start or operate without these)
- **prefect-server**: API coordination. Worker polls here for tasks. If down, worker loops idle until restart.
- **prefect-postgres**: Indirect. Server needs DB to queue tasks. Worker cannot fetch work if DB is down.

### Soft (degrade if these are down, but service still functional)
- **LiteLLM (dockp01)**: AI classification flows will fail or timeout (15s default).
- **Admin API**: Draft publish step fails; flow marked Failed.

### Reverse (services that depend on THIS service)
- **None (direct)**. Upstream flows depend on this worker being available to claim the `blog-pipeline-pool`.

## State & persistence

State is split between ephemeral execution context and persistent artifact storage.

- **Database tables**: None locally. Prefect state stored in `prefect-server` Postgres (`db-prefect` network).
- **Filesystem state**: `/mnt/docker/blog-drafts` on host `tmtdockp04`. Contains generated markdown/HTML. Growth rate: ? (depends on blog frequency). **Critical**: Not replicated.
- **In-memory state**: Flow run context. Lost on container restart.
- **External state**: None (Slack webhooks are outbound notifications only).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (polling) | > 80% sustained | Throttled by cgroup (`1.0`) |
| Memory | ~400MB | > 800MB | OOM killed (limit 1g) |
| Disk I/O | Low (idle) | N/A | Writes to `/mnt/docker/blog-drafts` |
| Network | Low (polling) | > 50MB/s egress | Dropped packets to LiteLLM cause flow failure |
| GPU (if applicable) | ? | ? | ? |
| Request latency p50 | 50ms (poll) | > 5s | Queue backlogs increase |
| Request rate | 1 req/min (idle) | N/A | Scales with active flow runs |

## Failure modes

- **Symptom**: Flows stuck in `Scheduled` status.
  - **Root cause**: Worker container restarted or network partitioned from `prefect-server`.
  - **Mitigation**: Restart container. Server Foreman service will re-queue `Running` tasks after 30s heartbeat timeout.
  - **Prevention**: Ensure `PREFECT_RUNNER_HEARTBEAT_FREQUENCY=30` matches server `FOREMAN_LOOP_SECONDS=30`.

- **Symptom**: Flow fails on artifact write.
  - **Root cause**: `/mnt/docker/blog-drafts` disk full or permission denied (UID 1000 mismatch).
  - **Mitigation**: Check host disk usage (`df -h`). Verify `user: "1000:1000"` matches host dir ownership.
  - **Prevention**: Monitor host disk usage alerts.

- **Symptom**: AI flows timeout/hang.
  - **Root cause**: LiteLLM (192.168.20.15) unreachable or overloaded.
  - **Mitigation**: Check LiteLLM health. Retry flow.
  - **Prevention**: Add circuit breaker to flow code (not in container config).

## HA constraints (input to fleet-reliability design)

This section dictates architectural limitations for replication or failover planning.

- **Replicable?**: **Yes, with coordination.** Can run on any host with access to `automation` network and `/mnt/docker/blog-drafts`.
- **Coordination requirements**: **None.** Prefect Server handles queue distribution. Multiple workers on `blog-pipeline-pool` will naturally load-balance.
- **State sharing across replicas**: **Shared Volume Required.** The `/app/drafts` mount points to host path `/mnt/docker/blog-drafts`. Replicas on other hosts **cannot** see the same files unless an external storage layer (NFS/Gluster) replaces the bind mount.
- **Hardware bindings**: **None.** No GPU or USB dependency.
- **Network constraints**: **Egress only.** Requires outbound access to `192.168.20.15:4000` (LiteLLM) and `192.168.20.18:4200`