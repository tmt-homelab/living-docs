

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "Unplanned outage acceptable for ≤ 1 hour" (CMDB: critical=false) |
| **Blast radius if down** | Users lose chat interface, RAG, tool calling UI. Backend inference (`vllm-chat`) and LiteLLM routing remain active. |
| **Recovery time today** | Auto-restart (Docker `unless-stopped`). Manual volume restore if DB corruption occurs. |
| **Owner** | ? (CMDB registered by `phase-1.4-bulk-backfill`, no human owner assigned) |

## What this service actually does

Open WebUI provides the user-facing Chat UI for the homelab AI fleet. It acts as a client to the LiteLLM API Gateway (`litellm:4000`) for LLM inference, RAG retrieval, and tool execution. It aggregates capabilities from external services: SearXNG (web search), Docling (document extraction), ComfyUI (image generation), and Qwen ASR/TTS (audio).

It is **not** an inference engine. It does not host models or perform vector search directly; it orchestrates calls to `litellm` and `milvus`. It is **not** a high-availability service currently; it relies on a local SQLite database stored in a Docker volume.

When this service is broken, users cannot interact with the fleet's AI capabilities via the web UI, though API clients using the LiteLLM endpoint directly remain unaffected.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `ghcr.io/open-webui/open-webui:latest` |
| **Pinning policy** | Tag-floating (`latest`). **Risk:** Unpinned updates may introduce breaking changes to API contracts with LiteLLM. |
| **Resource caps** | Memory limit: 4G. No CPU limit. No GPU reservation. |
| **Volumes** | `openwebui_data:/app/backend/data` (Named volume. **Contains state**: SQLite DB, user uploads). |
| **Networks** | `ai-services` (internal comms), `ai-inference` (to LiteLLM), `egress` (external APIs). |
| **Secrets** | 1Password Connect items: `openwebui-secret-key`, `litellm-owui-key`, `google-oauth-client-*`. |
| **Healthcheck** | `curl -sf http://127.0.0.1:8080/health` (Interval 30s, Timeout 10s, Retries 3). |

### Configuration shape

Environment variables drive all configuration. No external config file mount (unlike LiteLLM). Key groups:
- `OPENAI_API_BASE_URL`: Points to LiteLLM (`http://litellm:4000/v1`).
- `RAG_*`: Configures embedding (via LiteLLM), vector DB (Milvus), and web search (SearXNG).
- `AUDIO_*`: Points to external ASR/TTS on `192.168.20.17` (Dockp03).
- `IMAGE_GENERATION_*`: Points to ComfyUI on `192.168.20.16` (Dockp02).
- `ENABLE_*`: Feature flags (OAuth, Image Gen, Search).

## Dependencies

### Hard (service cannot start or operate without these)
- **`litellm`** — API Gateway. OWUI routes all LLM/RAG requests here. If down, 502s on all chat interactions.
- **`milvus-standalone`** — Vector DB (via `MILVUS_URI`). Required for RAG context retrieval.
- **`redis`** — Caching/Queue (via LiteLLM dependency chain).
- **`docker` network `ai-inference`** — Required to reach LiteLLM container.

### Soft (degrade if these are down, but service still functional)
- **`searxng`** (External) — Web search capability unavailable.
- **`comfyui`** (External IP `192.168.20.16`) — Image generation disabled.
- **`docling`** (External IP `192.1