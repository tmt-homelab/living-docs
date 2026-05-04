

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy/routing layer) |
| **Tolerable outage** | seconds–minutes (marked `critical: true` in CMDB; cascading impact on all AI consumers) |
| **Blast radius if down** | `openwebui` loses model routing, RAG embedding/reranking, and tool execution. `vane` synthesis halts. All MCP tool calls fail. External API consumers receive 502/503. No fallback inference path exists today. |
| **Recovery time today** | Auto-restart via `restart: unless-stopped`. Full functional recovery requires `litellm-postgres` + `redis` liveness (~15–30s). |
| **Owner** | `claude-code` (registered by) / `?` (human SRE) |

## What this service actually does

LiteLLM acts as the centralized OpenAI-compatible API gateway for the homelab AI stack. It authenticates requests, routes them to backend inference runners (`vllm-chat`, `vllm-embed`, `vllm-rerank`), applies caching, rate limiting, and usage auditing, and orchestrates MCP tool calls. Fleet consumers (`openwebui`, `vane`, external scripts) hit it via HTTP at `:4000`. It does **not** run models, host vector indexes, or process vision/audio payloads itself; it purely proxies, transforms, and logs traffic.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `ghcr.io/berriai/litellm:v1.82.3-stable` |
| **Pinning policy** | Tag-pinned only. No digest recorded. Rollback requires manual tag swap + compose up. |
| **Resource caps** | None defined in compose. Host CPU/RAM limits apply. |
| **Volumes** | `/mnt/docker/stacks/ai/litellm-config:/app/config:ro` (config.yaml + assets) <br> `/mnt/docker/stacks/ai/litellm-config/mcp_semantic_filter_hook.py` → overrides upstream hook path (read-only bind) <br> *No local state volumes.* |
| **Networks** | `ai-services`, `ai-inference`, `ai-mcp`, `db-ai`, `egress` (all external bridges) |
| **Secrets** | `LITELLM_MASTER_KEY`, `POSTGRES_PASSWORD`, `LITELLM_UI_USERNAME`, `LITELLM_UI_PASSWORD`, `SLACK_WEBHOOK_URL`, `DOCKER/HOMEASSISTANT/GITHUB/PREFECT/POWERDNS/CLOUDFLARE/PORTAINER/ARR_STACK/OVERSEERR/READONLY_SHARED_MCP_API_KEY` (sourced from `.env`/orchestrator) |
| **Healthcheck** | Python `urllib` to `http://127.0.0.1:4000/health/liveliness`. Interval 30s, timeout 10s, retries 5, start_period 120s. Fails if proxy process or DB connectivity is broken. |

### Configuration shape

Driven by `/app/config/config.yaml` (mounted RO). Env vars override/supplement config values for DB URLs, Redis targets, UI credentials, and MCP API keys. Config defines model routing groups (`chat`, `reason`, `code`), caching policies, callback endpoints, and hook registrations. The `mcp_semantic_filter_hook.py` bind mount patches an upstream proxy hook to prevent aggressive tool-stripping for non-MCP clients.

## Dependencies

### Hard (service cannot start or operate without these)
- `litellm-postgres` (Postgres 16) — stores API keys, audit logs, usage metrics, team/project config. Startup blocks until `service_healthy`.
- `redis` (Redis 8) — powers distributed caching, rate limiting, concurrency control, and session state. Startup blocks until `service_healthy`.
- `caddy` — ingress termination (per CMDB). Without it, external/untrusted clients cannot reach `:4000`.

### Soft (degrade if these are down, but service still functional)
- `vllm-chat`, `vllm-embed`, `vllm-rerank` — backend model runners. LiteLLM remains up but returns 503/routing errors for inference tasks.
- `searxng` (migrated to `dockp04`) — web search augmentation for RAG pipelines. Fails gracefully in OWUI/Vane.
- `milvus-*` stack — vector DB used by consumers, not directly queried by LiteLLM.

### Reverse (services that depend on THIS service)
- `openwebui` — primary consumer. Hits `http://litellm:4000/v1` for chat, embeddings, reranking, and tool execution. Complete UI paralysis without LiteLLM.
- `vane` — uses LiteLLM for LLM synthesis of search results.
- External CLI/automation — MCP clients and API-key-bearing scripts route through `:4000`.

## State & persistence

All state is externalized. LiteLLM itself is fully stateless.

- **Database**: `postgres://postgres:5432/litellm` on `litellm-postgres`. Holds `litellm_*` schemas for audit trails, token usage, API key rotation, team/project metadata, and callback logs. Growth: ~10–50MB/day under typical homelab load. Backed up via host PG dump schedule (unknown RPO/RTO in inputs).
- **Cache/Coordination**: `redis:6379`. Stores request/response cache entries, rate limit counters, concurrency locks, and session metadata. TTL-driven; no persistence required for proxy operation, but `appendonly yes` is enabled on the Redis container.
- **In-memory**: Connection pools, active routing state, hook contexts, loaded config. Lost on restart; rehydrated from DB/Redis/config.yaml.
- **Filesystem**: None. Config and hook patch are read-only. No local write mounts.
- **State sharing**: Fully shared via Postgres + Redis. Multiple replicas can coexist immediately.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------