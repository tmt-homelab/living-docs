

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | "hours" (non-critical search capability) |
| **Blast radius if down** | LiteLLM cannot route log-search queries; AI assistants lose SIEM visibility. No downstream outage for other MCPs. |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual intervention if secrets fetch fails. |
| **Owner** | `?` (CMDB registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Proxy for AI-assisted Splunk query execution. The `splunk-mcp` container exposes a FastMCP-compatible API over HTTP on the `ai-mcp` network. It translates LLM tool calls into Splunk Management API (port 8089) requests to search logs or retrieve metadata.

It is NOT a log collector or indexer. It does not store log data; it queries the existing Splunk instance running on `tmtdockp01`. It is not used for direct log ingestion or dashboard hosting. Consumers are strictly AI models routed via LiteLLM; no human SSH/console access is intended for this container.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local build (context: ./splunk)` |
| **Pinning policy** | None (local build context; requires `docker compose up --build`) |
| **Resource caps** | Not defined in compose (inherits Docker daemon defaults) |
| **Volumes** | `./shared:/app/shared:ro` (read-only shared config) |
| **Networks** | `ai-mcp` (Docker bridge, external) |
| **Secrets** | `services/splunk/username`, `services/splunk/password` (via SecretsProvider/1Password) |
| **Healthcheck** | `None` defined in compose |

### Configuration shape

Environment variables injected at startup via `x-secrets-env` plus service-specific overrides. Key service vars: `SPLUNK_HOST` (defaults to `${DOCKP01_IP}`), `SPLUNK_PORT: 8089`, `SPLUNK_SCHEME: https`, `SPLUNK_VERIFY_SSL: false`. SecretsProvider fetches credentials from 1Password Connect at boot; if 1Password is unreachable, falls back to Admin API (configurable via `ADMIN_API_URL`).

## Dependencies

### Hard (service cannot start or operate without these)
- **Splunk Management API** — Running on `tmtdockp01:8089`. If unreachable, MCP returns 502/timeout on all tool calls.
- **Secrets Provider** — Required for `SPLUNK_USERNAME`/`PASSWORD`. Startup hangs if Admin API and 1Password Connect both fail.
- **LiteLLM Gateway** — MCP is only reachable via `ai-mcp` network; LiteLLM must be running to route traffic.

### Soft (degrade if these are down, but service still functional)
- **1Password Connect** — Fallback to Admin API exists, but latency may increase.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI tool calls to this MCP. If down, search tools fail silently or error out in chat UI.
- **AI Assistants** — End-users lose log search capability.

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**: None. `./shared` volume is read-only. Container writes to ephemeral storage only (logs).
- **In-memory state**: Connection pools to Splunk. Lost on restart.
- **External state**: Splunk search jobs exist in the Splunk backend, not here.
- **Backup**: Not required for container. Configuration is Git-tracked in compose/env files.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | `<10%` (idle) | `>80%` sustained | N/A (stateless) |
| Memory | `~50-100MB` | `>500MB` | OOM kill if limit set |
| Disk I/O | Negligible | `N/A` | N/A |
| Network | Low (burst on query) | `>100Mbps` | TCP buffer fill |
| GPU | `None` | `N/A` | N/A |
| Request latency p50 | `?` (depends on Splunk query size) | `>5s` | Queue in LiteLLM |
| Request rate | `?` | `N/A` | N/A |

## Failure modes

- **SSL Verification Disabled**
  - **Symptom**: Container starts, but `SPLUNK_VERIFY_SSL: "false"` hides certificate errors.
  - **Root cause**: Internal Splunk cert likely self-signed.
  - **Mitigation**: Accept risk for homelab; verify cert validity manually if issues arise.
  - **Prevention**: Update Splunk container to use valid internal CA.
- **Secrets Fetch Hang**
  - **Symptom**: Container restarts loop; logs show `SecretsProvider` timeout.
  - **Root cause**: Admin API or 1Password Connect unreachable.
  - **Mitigation**: Check `ADMIN_API_URL` connectivity; restart SecretsProvider.
  - **Prevention**: Add liveness probe checking secret fetch status.
- **Network Isolation Mismatch**
  - **Symptom**: Connection refused to `SPLUNK_HOST`.
  - **Root cause**: Container on `ai-mcp` cannot route to host IP if Docker DNS fails.
  - **Mitigation**: Hardcode `DOCKP01_IP` in env vars.
  - **Prevention**: Use Docker service DNS names where possible.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless), but single-instance preferred per network segment.
- **Coordination requirements**: None. No leader election needed.
- **State sharing across replicas**: None. If replicated, both hit the same Splunk backend (Splunk handles query concurrency).
- **Hardware bindings**: None. No USB/GPU/NIC affinity.
- **Network constraints**:
  - Must attach to `ai-mcp` network (Docker bridge).
  - Cannot expose ports externally (security model relies on LiteLLM gateway).
  - Requires egress to `tmtdockp01:8089` (host IP routing).
- **Cluster size constraints**: Single instance per `ai-mcp` network segment recommended to avoid duplicate query costs and log noise. If scaling, requires LiteLLM load balancing config update.
- **Migration cost**: Low. Image is local build; moving to registry requires pushing `./splunk` artifact. Moving to another host requires re-running compose on target.

## Operational history

### Recent incidents (last 90 days)
- `2026-05-01` — CMDB record created via `phase-1.4-bulk-backfill`. No prior incident history in Corvus.

### Recurring drift / chronic issues
- **Build Context Drift**: Local build (`./splunk`) means `docker pull` doesn't work. Updates require `docker compose build`.
- **SSL Trust**: `SPLUNK_VERIFY_SSL: "false"` masks cert expiration risks.

### Known sharp edges
- **Host IP Dependency**: `SPLUNK_HOST` resolves to `${DOCKP01_IP}`. If `DOCKP01_IP` changes, service breaks until env updated.
- **Profile Gating**: Service is in `profile phase2`. `docker compose up` without flags will not start it.

## Open questions for Architect

- ? Why is `SPLUNK_VERIFY_SSL` explicitly disabled? Can we inject the internal CA into the container instead?
- ? Is `local build` intended for all MCPs, or should `splunk-mcp` be pulled from