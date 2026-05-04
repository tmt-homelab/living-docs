

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical search) |
| **Blast radius if down** | Open WebUI web-search feature fails; RAG web-retrieval degrades to local docs only |
| **Recovery time today** | Auto-restart (`unless-stopped`) + manual rollback if image drift |
| **Owner** | ? (CMDB registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

`vane` is a self-hosted AI search interface (Perplexity alternative). It accepts natural language queries, dispatches web searches to SearXNG, and synthesizes results using an LLM backend (via LiteLLM). It serves as the "web search" provider for the Open WebUI RAG pipeline.

Other services consume it via HTTP API. Open WebUI queries `vane` (exposed via `proxy` network/Caddy) to fetch search context for RAG enrichment. It is NOT an inference engine; it relies on external LLMs (`litellm` -> `vllm`) for synthesis. It is NOT a general purpose crawler; it delegates crawling to SearXNG.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `itzcrazykns1337/vane:slim-latest` |
| **Pinning policy** | Tag-floating (`latest`). **High risk** of silent drift or breaking changes. |
| **Resource caps** | None defined (relies on host defaults). CPU/Mem unconstrained. |
| **Volumes** | `vane_data` (named volume `ai_vane_data` at `/home/vane/data`). Contains state. |
| **Networks** | `ai-services`, `proxy` (external ingress via Caddy). |
| **Secrets** | None mounted. Env vars (API keys/URLs) embedded in compose or injected at runtime. |
| **Healthcheck** | `node -e "fetch(...:3000)"`. Checks HTTP 200 on internal port 3000. |

### Configuration shape

Configuration is exclusively environment-driven. Key vars: `SEARXNG_API_URL` (internal IP), `PUBLIC_URL`/`API_URL` (public FQDN). No `config.yaml` mounted; `vane_data` volume holds runtime state (cache/history).

## Dependencies

### Hard (service cannot start or operate without these)
- **SearXNG** (`192.168.20.18:8080`) — Web search backend. If down, Vane returns empty search results.
- **Proxy/Caddy** — Required for external ingress (`https://search-ai.themillertribe-int.org`).

### Soft (degrade if these are down, but service still functional)
- **LiteLLM** — If synthesis fails, Vane may return raw search results or error (depends on error handling in Vane code).

### Reverse (services that depend on THIS service)
- **Open WebUI** — Uses Vane for `RAG_WEB_SEARCH_ENGINE=searxng` flow via LiteLLM proxy. Breaks RAG web context.

## State & persistence

- **Database tables / schemas**: ? (Vane internal SQLite/DB likely in volume).
- **Filesystem state**: `/home/vane/data` (mounted to `ai_vane_data`). Contains config, cache, logs. Growth rate: Low (mostly JSON configs).
- **In-memory state**: Session caches. Lost on restart.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 50m | > 200m sustained | Throttles queries |
| Memory | < 512Mi | > 1Gi | OOMKilled (no limit set) |
| Disk I/O | Low (config writes) | High (cache churn) | N/A |
| Network | 10-50 KB/s | > 1MB/s sustained | Proxy timeout |
| Request latency p50 / p95 / p99 | ? / ? / ? | p99 > 10s | Queue buildup |
| Request rate | 5-20 req/min | > 100 req/min | Rate limited |

## Failure modes

- **Symptom**: Open WebUI search returns "No results".
  - **Root cause**: `SEARXNG_API_URL` unreachable or SearXNG down.
  - **Mitigation**: Verify SearXNG health (`192.168.20.18:8080`).
  - **Prevention**: Alert on SearXNG availability.

- **Symptom**: 502 Bad Gateway from Caddy.
  - **Root cause**: Vane container crashed or healthcheck failing.
  - **Mitigation**: `docker logs vane`, `docker restart vane`.
  - **Prevention**: Set memory limits to prevent OOM.

- **Symptom**: Unexpected behavior changes.
  - **Root cause**: Image tag `slim-latest` pulled new version.
  - **Mitigation**: Pin to specific digest immediately.
  - **Prevention**: Enforce digest pinning in compose.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (Stateful single-instance).
- **Coordination requirements**: None.
- **State sharing across replicas**: `ai_vane_data` is not shareable across replicas without conflict (local DB).
- **Hardware bindings**: None (CPU-only).
- **Network constraints**: Requires access to `proxy` network for ingress; `ai-services` for backend comms.
- **Cluster size constraints**: Single instance only (DB locking).
- **Migration cost**: Low (copy volume, update image). No data sync complexity.

## Operational history

### Recent incidents (last 90 days)
- ? (CMDB record created `2026-05-01`, backfilled. No incident history recorded).

### Recurring drift / chronic issues
- Image tag `slim-latest` drifts silently.
- SearXNG IP (`192.168.20.18`) hardcoded in Env; changes break connectivity.

### Known sharp edges
- **Memory**: No limit set. If synthesis loops, container can exhaust host RAM.
- **Ingress**: Relies on external Caddy config matching `PUBLIC_URL`.

## Open questions for Architect

- ? Pin image digest (current `slim-latest` violates fleet stability policy).
- ? Define backup strategy for `ai_vane_data` volume (is it included in ZFS snapshot policy?).
- ? Why CMDB `critical: false` but `dependencies: []` (ignores SearXNG)?

## Reference

- Compose: `homelab-ai/stacks/ai/docker-compose.yml`
- Logs: `/var/lib/docker/containers/vane/*.log` (json-file, 50m/3)
- Dashboards: ?
- Runbooks: ?
- Upstream docs: `https://github.com/itzcrazykns1337/vane`
- Related services: `litellm`, `openwebui`, `searxng` (external)