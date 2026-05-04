

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical per CMDB, but blocks API ingestion) |
| **Blast radius if down** | Programmatic image generation API (port 8189) fails. Admin dashboard job status goes stale. `comfyui` remains functional for direct web UI use. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Full recovery ~5m (queue replay if SQLite locked). |
| **Owner** | ? (bulk-backfill registration, no human assigned) |

## What this service actually does

`comfy-bridge` is an HTTP API proxy and job queue manager sitting in front of `comfyui`. It accepts JSON payloads, validates API keys, serializes tasks into a SQLite queue, and polls `comfyui` (internal service) for completion. It returns images and metadata to clients without exposing the ComfyUI internal API directly.

The fleet uses it for programmatic generation (CI/CD pipelines, admin dashboards, MCP servers). It handles authentication (`BRIDGE_API_KEY`) and workflow presets (predefined ComfyUI JSON graphs stored in `/app/presets`). It is NOT used for interactive manual generation (users go to `comfyui` web UI on 8188) and NOT used for model inference (GPU compute is isolated to `comfyui` container).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp02-comfyui/docker-compose.yml` |
| **Image** | `local build context (./bridge)` |
| **Pinning policy** | Local build (no registry tag). Updates via git pull + docker-compose up. |
| **Resource caps** | `memory: 2g`, `cpus: "1"`. No GPU reservation (uses CPU only). |
| **Volumes** | `comfy_bridge_queue` (named, state), `./presets` (ro), `/mnt/docker/data/comfyui/{input,output}` (shared rw with `comfyui`), `./bridge/*.py` (ro code) |
| **Networks** | `default` (internal), `secrets_default` (external API access) |
| **Secrets** | `BRIDGE_API_KEY`, `HF_TOKEN`, `ADMIN_API_TOKEN`, `SLACK_WEBHOOK_URL` (env vars from host/secrets) |
| **Healthcheck** | `GET http://127.0.0.1:8189/v1/health`. Interval 15s, timeout 5s, retries 3. |

### Configuration shape

Environment-driven. No config file loaded at runtime. Preset workflows are loaded from the mounted `./presets` directory as JSON/YAML. Queue location is hardcoded to `/tmp` (mapped to named volume). Connection to backend `comfyui` is hardcoded to `http://comfyui:8188`.

## Dependencies

### Hard (service cannot start or operate without these)
- **`comfyui`** — Backend inference engine. `depends_on` enforces startup order. If `comfyui` is unhealthy, bridge accepts jobs but cannot process them (queue blocks).
- **`secrets_default` network** — Required to reach `ADMIN_API_URL` and external HF endpoints.
- **Shared Host Storage (`/mnt/docker/data/comfyui`)** — Required to read/write input/output files.

### Soft (degrade if these are down, but service still functional)
- **`ADMIN_API_URL`** — Admin integration fails (no job logging/status sync), but image generation continues.
- **`SLACK_WEBHOOK_URL`** — Alerts fail, but service operates.

### Reverse (services that depend on THIS service)
- **External Clients (API users)** — All programmatic generation traffic routes here. If down, API returns 503.
- **`mcp_server` (mounted code)** — If bridge code mounts MCP server module, external MCP tools may depend on it. (Note: `mcp_server.py` is mounted as code, not a separate service).

## State & persistence

- **Queue (SQLite):** Located in `comfy_bridge_queue` named volume (mapped to `/tmp` in container). Contains job IDs, status, prompts, timestamps. **Critical.** If deleted, active jobs lost. Not replicated.
- **I/O State:** `/mnt/docker/data/comfyui/output` and `/input`. Shared with `comfyui`. Images written here by ComfyUI, read by Bridge for delivery. Growth rate depends on generation volume (unbounded).
- **Presets:** Stored in `./presets` bind mount. Read-only. Updated via git deployment.
- **In-memory:** Job polling state. Lost on restart (resumes from DB queue).
- **External:** HuggingFace cache (`/mnt/docker/data/comfyui/hf_cache`) is shared with `comfyui`.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (mostly I/O wait) | > 80% sustained | Throttled by CPU limit (1.0) |
| Memory | ~400MB - 800MB | > 1.8G | OOMKilled (limit 2G) |
| Disk I/O | Low (queue writes), High (image reads) | N/A | Bottlenecked by NVMe throughput |
| Network | Low (JSON control), High (image payload) | N/A | Limited by host NIC |
| GPU | 0% (Bridge does not compute)