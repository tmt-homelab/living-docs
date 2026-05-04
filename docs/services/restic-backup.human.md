

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "Backup window missed; no immediate app outage. RPO degrades by duration of outage." |
| **Blast radius if down** | "Recovery capability degraded. If host `tmtdockp04` fails, latest B2 snapshots remain accessible via `restic` CLI from elsewhere, but incremental chain continuity is at risk." |
| **Recovery time today** | "Manual trigger via `docker exec` or Prefect flow re-run." |
| **Owner** | "SRE Team (tmiller)" |

## What this service actually does

Restic backup agent running on `tmtdockp04`. It does not run a continuous backup loop internally. Instead, it maintains a persistent container state (`tail -f /dev/null`) to allow external triggers (Prefect flows, cron, scripts) to execute `restic backup` commands against it via `docker exec`.

It backs up critical host directories (`/mnt/docker`, `/mnt/media/infra/postgres`, etc.) to Backblaze B2 (`b2:tmt-backup:restic/dockp04`).

**Not used for:**
- Live application storage (all sources are read-only bind mounts).
- Real-time replication (batched snapshotting).
- Application-side HA coordination (it is a utility, not a consensus participant).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `restic/restic:0.17.3` |
| **Pinning policy** | Tag-floating (`0.17.3`). Not digest-pinned in CMDB; verify integrity on upgrade. |
| **Resource caps** | `memory: 2G`, `cpus: '2.0'` |
| **Volumes** | **Bind (RO):** `/mnt/docker`, `/mnt/docker-data`, `/mnt/media/infra/postgres`, `/mnt/media/hassbup`, `/mnt/media/ai/configs`. **Named:** `restic_cache` (`/root/.cache/restic`). |
| **Networks** | `automation` (external) |
| **Secrets** | 1Password Connect (injected via env vars: `RESTIC_PASSWORD`, `B2_ACCOUNT_ID`, `B2_ACCOUNT_KEY`) |
| **Healthcheck** | `none` (Container relies on process exit code of exec'd commands, not internal liveness) |

### Configuration shape

Configuration is purely environment-driven. No local config files.
- **Repo:** B2 bucket `tmt-backup`, path `restic/dockp04`.
- **Cache:** Local named volume `restic_cache` to speed up subsequent backups.
- **Sources:** Hardcoded bind mounts in compose; changes require compose redeploy.

## Dependencies

### Hard (service cannot start or operate without these)
- **Backblaze B2** — Network connectivity and valid credentials required for any backup/restore action.
- **Host Filesystem** — Direct access to `/mnt/...` paths on `tmtdockp04`. If host storage is mounted elsewhere, this service breaks.

### Soft (degrade if these are down, but service still functional)
- **Prefect Worker** — If Prefect is down, automated scheduling fails, requiring manual `docker exec` triggers.
- **1Password Connect** — Secrets rotation requires 1P availability to inject new tokens on redeploy.

### Reverse (services that depend on THIS service)
- **NemoClaw** — May query backup status via `/mnt/docker/backups` or API (needs verification).
- **Disaster Recovery Process** — The primary consumer of the output data.

## State & persistence

- **Database tables / schemas:** None.
- **Filesystem state:**
  - `restic_cache` (Named volume): Stores index/cache data. Low write frequency, high read frequency during backups.
  - Source directories (`/mnt/...`): Read-only. No state written here.
- **In-memory state:** None. Container is idle until `exec`'d.
- **External state:** B2 Object Store (Backblaze). Snapshots are immutable once finalized.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 0% (idle) | >80% during backup | Throttled at 2.0 cores |
| Memory | <500MB (cached) | >1.8GB | Kill on OOM (limit 2G) |
| Disk I/O | Low (cache) | High during scan | Bandwidth limited by host NIC |
| Network | Idle | >10Mbps sustained | B2 throttles if too aggressive |
| Request latency | N/A | N/A | N/A |
| Request rate | 0 req/s | 0 req/s | Triggered externally |

## Failure modes

- **Symptom:** Container running but no new B2 snapshots in last 24h.
  - **Root cause:** Scheduler (Prefect/Cron) failed to trigger `docker exec`.
  - **Mitigation:** Manually trigger `docker exec restic-backup restic backup ...`.
  - **Prevention:** Add healthcheck that verifies last snapshot timestamp (requires script wrapper).

- **Symptom:** `docker exec` fails with "container not running".
  - **Root cause:** Container died (OOM or crash) and `restart: on-failure` didn't catch it (if exit code 0 from exec).
  - **Mitigation:** Restart container.
  - **Prevention:** Ensure `entrypoint` stays alive (`tail -f /dev/null` is currently used).

- **Symptom:** B2 auth error.
  - **Root cause:** API keys rotated in 1Password but not redeployed.
  - **Mitigation:** Rotate env vars in 1P and redeploy stack.
  - **Prevention:** Alert on B2 API 403 errors (requires logging integration).

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Tied to host-specific filesystem paths (`/mnt/docker`, etc.). Cannot run on multiple nodes simultaneously for the same data.
- **Coordination requirements:** None. No distributed locking required for single-host backup.
- **State sharing across