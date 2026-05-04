

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Minutes (AI assistants degrade, core homelab unaffected) |
| **Blast radius if down** | LiteLLM AI routing fails for Home Assistant intents. No direct impact on HA availability. |
| **Recovery time today** | Auto-restart (`unless-stopped`) + SecretsProvider retry |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

`homeassistant-mcp` acts as a secure translation layer between the AI Gateway (LiteLLM) and the Home Assistant API. It accepts structured tool calls from the AI, validates them against `MCP_API_KEY`, translates them to Home Assistant REST/websocket commands, and returns results.

Primary purpose: Enable LLMs to query device states (sensors, switches) and trigger actions (lighting, scenes) within the `tmtdockp01`/`dockp04` ecosystem.

How it is NOT used: It does not host the Home Assistant UI. It does not store HA configuration. It does not handle direct user traffic (only AI Gateway traffic via `ai-mcp` network).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `build: ./homeassistant` (local context, no registry tag) |
| **Pinning policy** | Build context (manual rebuild required for code changes) |
| **Resource caps** | None defined in compose (defaults to host limits) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config share) |
| **Networks** | `ai-mcp` (Docker bridge, isolated from public) |
| **Secrets** | `services/homeassistant/ha_api_token`, `services/homeassistant-mcp/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | None defined in compose (rely on container restart policy) |

### Configuration shape

Configuration is driven at runtime via environment variables injected by the SecretsProvider wrapper.
- `HA_URL`: Points to `http://${DOCKP04_IP}:8123` (Home Assistant API endpoint).
- `MCP_API_KEY`: Shared bearer token validated against incoming LiteLLM requests.
- `ADMIN_API_URL`: Used for secret fetching (`http://${DOCKP04_IP}:8000`).

## Dependencies

### Hard (service cannot start or operate without these)
- **Home Assistant (`dockp04:8123`)**: Upstream API target. If down, MCP returns 503 errors to AI.
- **SecretsProvider (`Admin API`)**: Required to fetch `ha_api_token` and `MCP_API_KEY` at startup.
- **LiteLLM**: Consumer on the `ai-mcp` network. Without LiteLLM, no traffic flows to this service.

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **LiteLLM**: Routes AI intents. Breakage causes "Unable to control smart home" errors in chat interfaces.

## State & persistence

- **Database tables**: None.
- **Filesystem state**: None. `./shared` volume is mounted read-only.
- **In-memory state**: None. Connection state to HA is ephemeral.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 80% sustained | Throttles requests (no QoS defined) |
| Memory | ~50MB | > 500MB | OOM Kill |
| Network | Low (text payload) | > 10MB/s | Dropped packets |
| Request latency p50 / p95 | 50ms / 200ms | > 2s | Timeout errors to AI |
| Request rate | < 10 req/s | > 100 req/s | HA API rate limit hit |

## Failure modes

- **HA API Unreachable**:
    - **Symptom**: Latency spikes, 502 Bad Gateway from MCP.
    - **Root Cause**: `dockp04` HA container down or network route broken.
    - **Mitigation**: Restart `homeassistant-mcp` (won't help if HA is down). Check HA logs.
    - **Prevention**: HA High Availability cluster (outside this service scope).
- **Token Expiration**:
    - **Symptom**: `401 Unauthorized` on all tool calls.
    - **Root Cause**: `ha_api_token` rotated but not updated in SecretsProvider.
    - **Mitigation**: Update 1Password item `services/homeassistant/ha_api_token`, trigger redeploy.
    - **Prevention**: Rotate token secrets with versioned paths.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless). Can run N instances behind a load balancer.
- **Coordination requirements**: None. No leader election needed.
- **State sharing across replicas**: None. All state resides in Home Assistant backend.
- **Hardware bindings**: None. Purely networked service.
- **Network constraints**:
    - Must reside on `ai-mcp` network to reach LiteLLM.
    - Must reach `DOCKP04_IP` (host routing) for HA backend.
    - Cannot expose ports to external networks (security risk).
- **Cluster size constraints**: None. Limited only by HA API rate limits (single backend bottleneck).
- **Migration cost**: Low. Copy config, start new container, swap DNS/IP.
- **Critical Constraint**: The backend (Home Assistant) is single-instance stateful (`Class 3`). Scaling `home