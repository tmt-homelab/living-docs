

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours for CI/CD deploys; Minutes for runtime image pulls |
| **Blast radius if down** | CI/CD pipeline stalls on image push; `corvus` cannot pull new images (recovery requires host-level image load) |
| **Recovery time today** | Auto-restart (`always`); Manual restore from backup if volume corrupt |
| **Owner** | ? (phase-1.4-bulk-backfill) |

## What this service actually does

Stores Docker images locally to decouple homelab fleet from GHCR rate limits and external availability. The fleet uses it as the internal artifact store. When it's broken, new deploys cannot pull the latest `corvus` image, and CI pipelines fail on `docker push`.

It is NOT used for:
- General file storage (use NFS/SMB for that).
- Secret management (use 1Password/Pass).
- Long-term retention (images are ephemeral; garbage collection is manual or non-existent).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-corvus/docker-compose.yml` |
| **Image** | `registry:2` |
| **Pinning policy** | Tag-floating (`:2`) — risk of upstream API drift |
| **Resource caps** | None defined (unbounded) |
| **Volumes** | `registry-data:/var/lib/registry` (Stateful) |
| **Networks** | Default bridge (implicit) |
| **Secrets** | None (unauthenticated by default) |
| **Healthcheck** | `none` (no probe defined in service block) |

### Configuration shape

Minimal config. Relies on Docker daemon defaults. No `config.yml` mounted for storage backend or TLS. Environment variables passed by Docker daemon defaults.

## Dependencies

### Hard (service cannot start or operate without these)
- None (self-contained binary)

### Soft (degrade if these are down, but service still functional)
- `tmtdockp04` host disk I/O (slowdowns affect pull latency)
- Docker Daemon (service restarts if daemon restarts)

### Reverse (services that depend on THIS service)
- `corvus` — pulls `localhost:5000/corvus:latest`. Breaks if registry unreachable during image pull phase.
- `GitHub Actions` — pushes images here during `deploy` workflow.

## State & persistence

**State is entirely filesystem-based.** No database layer.

- **Database tables / schemas:** N/A
- **Filesystem state:**
  - Path: `/var/lib/registry` (mapped to `registry-data` volume)
  - Content: Blob storage (sha256 hashes), Manifests, Indexes.
  - Growth rate: Proportional to `corvus` build frequency (approx. 500MB/week estimated).
- **In-memory state:** None (stateless process logic, state on disk).
- **External state:** None.

**Backup Strategy:**
- RPO: Unknown (no automated snapshot defined).
- RTO: Manual volume copy restore.
- Shareable: No. Volume is bound to `tmtdockp04` host storage.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% idle | > 80% sustained | Throttles pulls/pushes |
| Memory | < 100MB | > 512MB | OOM kill if host constrained |
| Disk I/O | Low | > 80% inode usage | Pushes fail immediately |
| Network | < 10Mbps | > 90%