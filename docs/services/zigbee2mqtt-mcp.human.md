

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Minutes (non-critical control plane) |
| **Blast radius if down** | AI assistants lose ability to query/control Zigbee devices (lights, sensors, locks). Home Assistant UI unaffected. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Manual redeploy if config drift detected. |
| **Owner** | `?` (Registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Proxies AI LLM model requests to the Zigbee2MQTT backend API. It translates AI natural language or tool-calling into HTTP calls against the Zigbee2MQTT instance running on `DOCKP04_IP:8080`.

- Primary purpose: Enable AI agents to read device states and issue commands (toggle, brightness, color) via Zigbee network.
- Consumer pattern: HTTP API. Only reachable by `LiteLLM` via the `ai-mcp` Docker network.
- What it is NOT: It does not communicate with Zigbee hardware directly. It does not store device state (that lives on the Z2M backend on DOCKP04). It does not expose ports to the public internet.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Local build (`context: ./zigbee2mqtt`) |
| **Pinning policy** | Local build context (tag floating/unknown) |
| **Resource caps** | `?` (None defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (Read-only config/scripts) |
| **Networks** | `ai-mcp` (External Docker bridge) |
| **Secrets** | `services/readonly-shared/mcp_api_key` (via SecretsProvider) |
| **Healthcheck** | `?` (Not defined in compose) |

### Configuration shape

Environment variables injected via `x-secrets-env` macro + service-specific overrides.
- `Z2M_URL`: Points to backend Zigbee2MQTT instance (`http://${DOCKP04_IP}:8080`).
- `MCP_API_KEY`: Shared bearer token for LiteLLM authentication.
- Secrets fetched at container startup via `SecretsProvider` (Admin API or 1Password Connect).

## Dependencies

### Hard (service cannot start or operate without these)
- **LiteLLM** — Gateway. All traffic enters here. If LiteLLM is down, MCP is unreachable.
- **Zigbee2MQTT Backend** — Running on `DOCKP04_IP:8080`. If Z2M API is unreachable, this service returns 5xx errors.
- **SecretsProvider** — Required for startup. If Admin API or 1Password Connect is unreachable, container exits (no secrets = no auth).

### Soft (degrade if these are down, but service still functional)
- None.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI tool calls to this endpoint.
- **AI Assistants** — Indirect consumers via LiteLLM.

## State & persistence

- **Database tables**: None (Proxy only).
- **Filesystem state**: None. `./shared` mount is read-only.
- **In-memory state**: Session state lost on restart. No persistent cache.
- **External state**: All device state resides on Zigbee2MQTT backend (DOCKP04).
- **Backups**: N/A for this container.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 1% (idle) | > 50% sustained | Throttled by Docker |
| Memory | < 128MB | > 512MB | OOM Kill |
| Disk I/O | Negligible | ? | ? |
| Network | < 1MB/s | > 100MB/s | ? |
| GPU | None | ? | ? |
| Request latency p50 / p95 / p99 | ? / ? / ? | > 5s | Timeout |
| Request rate | Low (IoT events) | > 100 req/s | Queue backlog |

## Failure modes

- **Symptom**: AI reports "Device unreachable" or "Timeout".
  - **Root cause**: Zigbee2MQTT backend (`DOCKP04_IP:8080`) is down or network partitioned.
  - **Mitigation**: Check DOCKP04 Z2M container status.
  - **Prevention**: Z2M healthchecks.

- **Symptom**: Container restarts loop at startup.
  - **Root cause**: SecretsProvider cannot fetch `MCP_API_KEY` (Admin API or OP Connect down).
  - **Mitigation**: Check `ADMIN_API_URL` connectivity and `OP_CONNECT_HOST`.
  - **Prevention**: Monitor SecretsProvider endpoints.

- **Symptom**: 401 Unauthorized from LiteLLM.
  - **Root cause**: `MCP_API_KEY` drift or expiration.
  - **Mitigation**: Rotate secret in 1Password/Admin API, redeploy container.
  - **Prevention**: Secret rotation policy automation.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (Stateless proxy logic).
- **Coordination requirements**: None. No leader election needed.
- **State sharing across replicas**: None. Each instance connects independently to Z2M backend.
- **Hardware bindings**: None. Zigbee hardware is attached to DOCKP04, not this host (`tmtdockp01`).
- **Network constraints**:
  - Must reside on `ai-mcp` network ONLY.
  - Cannot reach external internet directly (egress restricted via network isolation).
  - Must resolve `DOCKP04_IP` (hardcoded env var) to reach Z2M backend.
- **Cluster size constraints**: Single-instance deployment currently. Scaling to multiple replicas would require load balancing at LiteLLM (currently not configured).
- **Migration cost**: Low. Container is stateless; redeploying to another host requires only updating `DOCKP04_IP` env var if backend moves.

## Operational history

### Recent incidents (last 90 days)
- `2026-05-01` — Bulk backfill registration (Phase 1.4). No incidents recorded yet.

### Recurring drift / chronic issues
- `DOCKP04_IP` environment variable must be updated manually if DOCKP04 IP address changes (DHCP/static lease drift).

### Known sharp edges
- `Z2M_URL` uses `http` scheme (unencrypted). Trust boundary is internal `ai-mcp` network.
- SecretsProvider fallback logic (Admin API → 1Password) adds startup latency if Admin API is slow.

## Open questions for Architect

- ? Healthcheck implementation: Should we add a TCP check against `Z2M_URL` to detect backend failure early?
- ? Scaling: Is LiteLLM configured to support multiple `zigbee2mqtt-mcp` instances for load distribution, or is this strictly single-instance?
- ? Image pinning: Local build context `./zigbee2mqtt` makes version tracking difficult. Should we move to a tagged registry image?

## Reference

- Compose: `homelab-automation/stacks/mcp-servers/docker-compose.yml`
- Logs: `docker logs zigbee2mqtt-mcp` (json-file, max 30MB total)
- Dashboards: ? (No Grafana panel specific to this MCP)
- Runbooks: ?
- Upstream docs: ? (Internal MCP standard)
- Related services: `homeassistant-mcp` (similar IoT control), `zigbee2mqtt` (backend on DOCKP04)