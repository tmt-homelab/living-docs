

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | `unplanned outage acceptable for ≤ 4 hours` (Log buffering allows catch-up) |
| **Blast radius if down** | Log ingestion stops → Splunk indices stale → Security audit gap; no direct impact on AI availability |
| **Recovery time today** | `auto-restart` (unless-stopped) + manual volume inspection |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill` automation) |

## What this service actually does

Shrike acts as a log normalization gateway. It accepts JSON log batches via HTTP POST at `/v1/ingest`, normalizes them to the OCSF schema, and routes them to Splunk HEC endpoints. It is the only service in the fleet that performs OCSF transformation before external delivery.

Fleet services (e.g., `lite-lm`, `auth-proxy`) push logs to Shrike's API rather than shipping directly to Splunk. This centralizes schema enforcement and TLS termination. Shrike is NOT used for long-term storage; it relies on Splunk for retention. It is also NOT a message queue; it does not guarantee delivery if Splunk is unreachable beyond its local WAL buffer.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp01-shrike/docker-compose.yml` |
| **Image** | `dockp04:5000/shrike:full-ml:full-ml` |
| **Pinning policy** | `tag-floating` (Tag `full-ml` moves; no digest pinned) |
| **Resource caps** | `?` (Not defined in compose; relies on docker default) |
| **Volumes** | `shrike-data:/data` (Stateful WAL storage); No bind mounts |
| **Networks** | `ai-services` (External bridge) |
| **Secrets** | 1Password Connect (Injected as Env Vars: `SPLUNK_HEC_TOKEN`, `INGEST_API_KEY`, etc.) |
| **Healthcheck** | `GET http://localhost:8080/health` (30s interval, 5s timeout) |

### Configuration shape

Environment variables drive all behavior. No config files mounted. Key variables control destination (`SPLUNK_HEC_URL`), security (`INGEST_API_KEY`), and persistence (`SHRIKE_WAL_MAX_MB`). TLS verification for Splunk is toggleable via `SHRIKE_SPLUNK_TLS_VERIFY` (default `false`).

## Dependencies

### Hard (service cannot start or operate without these)
- **Splunk HEC** — Log destination. If unreachable, logs buffer in WAL until disk full.
- **1Password Connect** — Secret injection. If down, container fails to resolve secrets (env vars empty).

### Soft (degrade if these are down, but service still functional)
- **None** — Service runs independently of other fleet nodes.

### Reverse (services that depend on THIS service)
- **Log Producers** — Any service sending to `http://tmtdockp01:8082`. Breakage causes client-side log loss if buffer fills.

## State & persistence

- **Database tables**: None.
- **Filesystem state**: `/data/wal` (Write-Ahead Log). Stores unflushed log batches. Growth rate unknown; capped at `SHRIKE_WAL_MAX_MB` (2048 MB).
- **In-memory state**: Active log batches awaiting HEC acknowledgment. Lost on restart.
- **External state**: Splunk Indexer. Shrike has no copy; once sent, data is out of scope.
- **Backup**: `shrike-data` volume is not explicitly backed up in compose. RPO depends on WAL flush frequency.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | `?` | `?` | Throttled by host limits |
| Memory | `?` | `?` | GC pressure on large batches |
| Disk I/O | `?` | `?`