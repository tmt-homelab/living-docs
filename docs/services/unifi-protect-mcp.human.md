

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical) |
| **Blast radius if down** | AI agents lose ability to query UniFi Protect cameras, motion events, or NVR status. No impact on video recording or network traffic. |
| **Recovery time today** | Auto-restart (`unless-stopped`) + manual redeploy if config drift |
| **Owner** | ? |

## What this service actually does

Acts as a secure Model Context Protocol (MCP) proxy for UniFi Protect NVR APIs. It translates AI model requests into authenticated HTTP calls against the Protect controller.

- **Primary purpose:** Expose camera feeds, device status, and motion events to the AI fleet (via LiteLLM).
- **Consumer pattern:** HTTP API (MCP protocol) over Docker bridge network `ai-mcp`.
- **Not used for:** Video storage, network routing, or general UniFi network management (handled by `unifi-network-mcp`).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (context: `./unifi-protect-mcp`) |
| **Pinning policy** | None (local build context) |
| **Resource caps** | ? (No limits defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only shared config) |
| **Networks** | `ai-mcp` (external Docker bridge) |
| **Secrets** | SecretsProvider (1Password Connect / Admin API). Specific item paths not documented in compose comments for this service. |
| **Healthcheck** | None defined in compose |

### Configuration shape

Environment variables injected at startup. Critical values sourced from `SecretsProvider` or deploy workflow env vars.

- `PROTECT_HOST`: Target NVR IP/Hostname (e.g., `http://${PROTECT_HOST}`).
- `PROTECT_API_KEY`: API token for NVR authentication.
- `PROTECT_PORT`: `443` (hardcoded).
- `PROTECT_VERIFY_SSL`: `false` (accommodates self-signed UniFi certs).
- `MCP_API_KEY`: Auth token for incoming MCP connections (specific `${UNIFI_PROTECT_MCP_API_KEY}` or fallback to shared).

## Dependencies

### Hard (service cannot start or operate without these)
- **UniFi Protect NVR (`PROTECT_HOST`)** — Service cannot authenticate or fetch data if NVR is unreachable.
- **`ai-mcp` Network** — Required for communication with LiteLLM gateway.
- **Secrets Provider** — Startup fails if Admin API/1Password unreachable (no fallback secrets in container).

### Soft (degrade if these are down, but service still functional)
- None (stateless proxy).

### Reverse (services that depend on THIS service)
- **LiteLLM Gateway** — Routes AI requests to this MCP server.
- **AI Models/Agents** — Lose visibility into camera streams/events if this service is down.

## State & persistence

- **Database tables / schemas:** None (stateless).
- **Filesystem state:** None writable. Mount `./shared` is read-only.
- **In-memory state:** Active HTTP sessions (lost on restart).
- **External state (S3, etc.):** None.
- **Backup:** N/A. Configuration is ephemeral (Env vars + Secrets).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% | > 50% sustained | ? |
| Memory | ~150MB | > 500MB | ? |
| Disk I/O | Negligible | N/A | N/A |
| Network | Bursty (polling) | N/A | ? |
| GPU (if applicable) | N/A | N/A | N/A |
| Request latency p50 / p95 / p99 | < 200ms | > 2s | ? |
| Request rate | Low (polling based) | ? | ? |

## Failure modes

- **SSL Handshake Failure**
  - **Symptom:** Container logs show TLS errors; AI agents return "connection refused".
  - **Root cause:** `PROTECT_VERIFY_SSL` set to `true` against self-signed UniFi cert.
  - **Mitigation:** Ensure `PROTECT_VERIFY_SSL: "false"` in env.
- **API Key Rotation**
  - **Symptom:** 401 Unauthorized on all requests.
  - **Root cause:** NVR API key changed, not updated in SecretsProvider.
  -