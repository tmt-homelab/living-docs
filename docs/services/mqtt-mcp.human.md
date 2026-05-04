

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour |
| **Blast radius if down** | AI assistants lose MQTT topic read/write capability via LiteLLM |
| **Recovery time today** | Auto-restart (`unless-stopped`) |
| **Owner** | `phase-1.4-bulk-backfill` (Automation) |

## What this service actually does

Provides the Model Context Protocol (MCP) interface for interacting with the homelab MQTT broker. It allows AI models connected through the LiteLLM gateway to publish messages to topics and subscribe to live telemetry or control events.

The container is a thin proxy: it does not host the MQTT broker itself. It authenticates via `MCP_API_KEY` and forwards requests to the backend broker at `MQTT_URL`. It is used primarily for IoT state retrieval and device control commands triggered by LLM agents.

It is NOT used for direct MQTT client connections (e.g., Home Assistant devices do not connect to this container). It is NOT the broker (that resides at `DOCKP04_IP:1883`).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build (./mqtt context)` |
| **Pinning policy** | None (local build context) |
| **Resource caps** | ? (Not defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config/shared data) |
| **Networks** | `ai-mcp` (Docker bridge, external) |
| **Secrets** | `MCP_API_KEY` (via SecretsProvider/1Password), `ADMIN_API_TOKEN`, `OP_CONNECT_TOKEN` |
| **Healthcheck** | none |

### Configuration shape

Environment variables are injected via `x-secrets-env`. Key operational vars: `MQTT_URL` (backend broker address), `ADMIN_API_URL` (for secrets retrieval). No persistent config files; all state passed via env vars at startup. Secrets fetched dynamically via `SecretsProvider().get_secret(path)` at container init.

## Dependencies

### Hard (service cannot start or operate without these)
- **MQTT Broker** (`${DOCKP04_IP}:1883`) — Service fails to connect if broker is unreachable.
- **SecretsProvider** (`ADMIN_API_URL` or `OP_CONNECT_HOST`) — Service cannot start without valid `MCP_API_KEY`.
- **Docker Network** (`ai-mcp`) — Container requires this network to route traffic to LiteLLM.

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI requests to this MCP server. If down, AI cannot interact with MQTT.
- **AI Assistants** — End-user agents relying on IoT control.

## State & persistence

- **Database tables / schemas**: ? (Likely none)
- **Filesystem state**: `/app/shared` (mounted read-only, no writes). Logs stored in Docker json-file (`/var/lib/docker/containers/...`).
- **In-memory state**: Connection state to MQTT broker (lost on restart).
- **External state (S3, etc.)**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | Low (logs only) | ? | ? |
| Network | Low (keepalive + events) | ? | ? |
| GPU (if applicable) | ? | ? | ? |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom**: Logs show `ConnectionRefused` to `MQTT_URL`.
  - **Root cause**: Broker at `DOCKP04` down or network routing broken.
  - **Mitigation**: Verify broker status on `DOCKP04`. Check `ai-mcp` network routing.
  - **Prevention**: Ensure broker has alerting independent of MCP fleet.

- **Symptom**: Container exits immediately.
  - **Root cause**: Secrets fetch failure (1Password/Admin API unreachable).
  - **Mitigation**: Check `OP_CONNECT_HOST` connectivity. Verify `ADMIN_API_TOKEN`.
  - **Prevention**: Add healthcheck dependency on secrets endpoint (not currently implemented).

- **Symptom**: `ai-mcp` network unreachable.
  - **Root cause**: Docker network driver failure or host restart.
  - **Mitigation**: Recreate `ai-mcp` network. Restart container.
  - **Prevention**: Monitor Docker daemon health on `tmtdockp01`.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes. Container is stateless; multiple instances can run simultaneously without coordination.
- **Coordination requirements**: None. No leader election required.
- **State sharing across replicas**: None. Each instance maintains its own MQTT connection.
- **Hardware bindings**: None. No USB/GPU requirements.
- **Network constraints**: Must be attached to `ai-mcp` network. Cannot expose ports to public internet (security policy). Must reach `DOCKP04` via host routing (Docker service DNS does not cross hosts).
- **Cluster size constraints**: Currently single-instance (`tmtdockp01`). No quorum requirements.
- **Migration cost**: Low. Moving to a new host requires updating `DOCKP04_IP` env var if using static IP, or ensuring DNS resolution works across subnets. Network attachment (`ai-mcp`) must be recreated on target host.
- **Blast radius of scaling**: High. Scaling to N instances means N MQTT connections to the backend broker. Broker connection limits must be checked before horizontal scaling.

## Operational history

### Recent incidents (last 90 days)
- None recorded in Corvus.

### Recurring drift / chronic issues
- None observed.

### Known sharp edges
- **Network Isolation**: `ai-mcp` is external. If the network is deleted, all 21 MCP servers lose connectivity simultaneously. Do not recreate network without reattaching services.
- **Secrets Rotation**: Secrets are fetched at startup. Key rotation requires container restart.
- **Broker Auth**: `MCP_API_KEY` is shared across many MCP servers. Compromise of this key exposes all IoT controls.

## Open questions for Architect

- ? Should