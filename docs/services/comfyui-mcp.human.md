

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Minutes (non-critical feature) |
| **Blast radius if down** | LiteLLM image-gen routing fails for ComfyUI workflows; AI assistants cannot trigger local Stable Diffusion/ComfyUI pipelines |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual restart if secrets fetch fails |
| **Owner** | ? (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

`comfyui-mcp` acts as a Model Context Protocol (MCP) server bridge for the ComfyUI image generation backend. It allows LLM clients (via LiteLLM gateway) to issue structured requests for image generation workflows without exposing the ComfyUI API directly.

Primary purpose: Translate MCP tool calls (e.g., `generate_image`) into ComfyUI API requests. It does not run the ComfyUI backend itself; it proxies to a remote ComfyUI instance.

How other fleet services use it:
- **LiteLLM**: Routes image generation prompts to this container via the `ai-mcp` network.
- **SecretsProvider**: Injects authentication credentials at container startup.

What it is NOT used for:
- Heavy model inference (GPU tasks happen on the target ComfyUI host).
- Persistent storage of generated images (handled by target ComfyUI).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `mcp-servers_comfyui-mcp:latest` (built from `./comfyui` context) |
| **Pinning policy** | Build context (volatile) |
| **Resource caps** | Unknown (no `deploy.resources` defined) |
| **Volumes** | `./shared:/app/shared:ro` (read-only shared config) |
| **Networks** | `ai-mcp` (isolated bridge) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | ? (not defined in compose snippet) |

### Configuration shape

Configuration is primarily environment-driven via `*secrets_env` inheritance.
- **MCP Auth**: `MCP_API_KEY` validated via `SecretsProvider`.
- **Target URL**: **Gap detected**. Unlike `homeassistant-mcp` (`HA_URL`) or `splunk-mcp` (`SPLUNK_HOST`), no explicit `COMFYUI_URL` or `TARGET_COMFYUI` variable is visible in the compose environment block. It may be hardcoded in the `./comfyui` Dockerfile or fetched via an undocumented secret path.
- **Logging**: `json-file`, max 10MB per file, 3 files retained.

## Dependencies

### Hard (service cannot start or operate without these)
- **SecretsProvider**: Required to fetch `MCP_API_KEY` and admin tokens. Container may fail to start if Admin API/1Password unreachable.
- **LiteLLM**: Primary consumer. Without LiteLLM, this service has no traffic source.
- **Target ComfyUI Instance**: Logical dependency (not in CMDB). If the backend ComfyUI is down, this service returns errors despite running healthy.

### Soft (degrade if these are down, but service still functional)
- **Shared Volume (`./shared`)**: Read-only mount. If host filesystem is read-only, service runs; if volume missing, startup may fail depending on app init.

### Reverse (services that depend on THIS service)
- **LiteLLM**: Depends on this for image generation tool calls. Failure blocks all AI image gen workflows routed through this node.

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**: None. Container is ephemeral.
- **In-memory state**: API session state (lost on restart).
- **External state**: None. Target ComfyUI handles image storage.
- **Backup**: Not required (stateless).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (<5%) | >50% sustained | Queueing requests if backend slow |
| Memory | ? | >80% | OOM kill if backend buffering large payloads |
| Disk I/O | Negligible | N/A | N/A |
| Network | Low (keepalive) | >500Mbps | Dropped connections if `ai-mcp` saturated |
| GPU | None | N/A | N/A |
| Request latency p50 / p95 / p99 | ? / ? / ? | p99 > 