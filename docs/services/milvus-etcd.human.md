

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (Milvus metadata unavailable → vector search fails) |
| **Blast radius if down** | `milvus-standalone` fails startup/healthcheck → `openwebui` RAG/Hybrid search returns errors → all AI knowledge retrieval degraded |
| **Recovery time today** | Auto-restart (`unless-stopped`); Data restore requires manual volume backup restoration |
| **Owner** | AI Stack Team (homelab-ai) |

## What this service actually does

Provides metadata coordination for `milvus-standalone`. Stores schema definitions, collection metadata, and index configurations for the Milvus vector database.
-   **Primary purpose**: Distributed key-value store acting as Milvus' metadata backend.
-   **How fleet uses it**: `milvus-standalone` connects via TCP `2379` on the `db-vector` network.
-   **NOT used for**: Vector payload storage (handled by `milvus-minio`), query processing (handled by `milvus-standalone`), or persistent object storage.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `quay.io/coreos/etcd:v3.5.18` |
| **Pinning policy** | Tag-floating (`v3.5.18`) — no digest pinned in current manifest |
| **Resource caps** | CPU/Mem limits undefined (inherits host defaults) |
| **Volumes** | `etcd_data:/etcd` (Named volume, stateful) |
| **Networks** | `db-vector` |
| **Secrets** | None (uses default minio credentials via env vars passed to Milvus, not etcd directly) |
| **Healthcheck** | `etcdctl endpoint health`, interval 30s, timeout 10s, retries 3 |

### Configuration shape

Minimal configuration. Runs as single-node cluster.
-   **Endpoints**: Advertises `127.0.0.1:2379` but listens on `0.0.0.0:2379`.
-   **Data Dir**: `/etcd` inside container, mapped to `etcd_data` volume.
-   **Env**: None defined explicitly; inherits `NVIDIA_VISIBLE_DEVICES=""` (CPU-only constraint).

## Dependencies

### Hard (service cannot start or operate without these)
-   None (runs standalone)

### Soft (degrade if these are down, but service still functional)
-   None

### Reverse (services that depend on THIS service)
-   `milvus-standalone` — Critical dependency. Fails to start or maintain cluster state without etcd.
-   `openwebui` — Indirectly dependent via Milvus for RAG.

## State & persistence

-   **Database tables / schemas**: N/A (Key-value store)
-   **Filesystem state**: `/etcd` (Volume `ai_etcd_data`). Contains snapshot files (`snap`), WAL logs (`member/wal`). Grows with metadata churn (collection creation/dropping).
-   **In-memory state**: In-memory store of KV pairs. Lost on restart if volume missing.
-   **External state**: None.
-   **Backup status**: **Unknown**. Volume `etcd_data` exists but no backup schedule documented in CMDB or compose.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (<5%) | >50% sustained | N/A |
| Memory | ~100-200MB | >1GB | N/A |
| Disk I/O | Low (WAL writes) | High latency | WAL disk fill → etcd leader election failure |
| Network | Low (Heartbeats) | High packet loss | N/A |
| Request latency p50 / p95 / p99 | <5ms / <10ms | >50ms | N/A |
| Request rate | Low (Control plane) | N/A | N/A |

## Failure modes

-   **Symptom**: `milvus-standalone` healthcheck fails (`403 Forbidden` or connection refused).
-   **Root cause**: Etcd leader election timeout or disk full (WAL).
-   **Mitigation**: Restart `milvus-etcd` container; check volume disk usage.
-   **Prevention**: Monitor `/etcd` volume growth; enforce disk quota.

-   **Symptom**: `milvus