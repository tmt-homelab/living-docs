

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | 15 minutes (Control plane degradation; flows queue in Prefect) |
| **Blast radius if down** | `prefect-worker` loses DNS/HA update capability; `nemoclaw` loses CMDB sync; external GitOps pipelines fail on `/gitops` endpoints. |
| **Recovery time today** | Auto-restart (`restart: always`); manual intervention if Docker socket permissions drift. |
| **Owner** | `tmiller` (human); `claude-code` (registered_by) |

## What this service actually does

Central utility API for homelab operational governance. It acts as the abstraction layer between automation workers (Prefect, NemoClaw) and external control planes (Home Assistant, PowerDNS, GitHub, Docker hosts). It exposes endpoints for DNS management, host registry queries, and GitOps triggers. It does NOT run flows itself; it coordinates the *state* of the infrastructure that flows execute against.

Consumer pattern: HTTP API (JSON). Workers call `http://admin-api:8000` for action execution (e.g., "Update DNS record", "Reboot Host"). It is not used for general application traffic; it is strictly internal ops traffic.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `prefect-admin-api:latest` (Local build from `/mnt/docker/stacks/dockp04-automation/admin-api`) |
| **Pinning policy** | Tag-floating (`latest`); built on CI/CD deploy |
| **Resource caps** | `?` (None defined in compose) |
| **Volumes** | `/var/run/docker.sock` (Stateful access), `admin_api_data:/data` (SOP DB), `/Users/tmiller/.ssh` (Identity), `/certs/docker` (TLS), `/mnt/docker/stacks` (Read-only config) |
| **Networks** | `infra-services`, `automation` |
| **Secrets** | 1Password Connect (`OP_CONNECT_*`), Env vars (`ADMIN_API_TOKEN`, `MCP_API_KEY`, `GITHUB_TOKEN`) |
| **Healthcheck** | `curl -f http://127.0.0.1:8000/health` (30s interval) |

### Configuration shape

Configuration is purely environment-driven. No external config files loaded at runtime.
- **Auth:** `ADMIN_API_KEYS` (format `name:key`).
- **Integrations:** Hosts defined via IP (HA, PowerDNS, Milvus) or DNS (Prefect).
- **TLS:** `DOCKER_TLS_ENABLED=true` enables mutual auth for remote Docker hosts.
- **Secrets:** Sourced from 1Password Connect at container start; no secrets in compose file.

## Dependencies

### Hard (service cannot start or operate without these)
- `op-connect-api` (CMDB reference) — 1Password Connect sidecar/service for secret injection.
- `Docker Daemon` — Required via `/var/run/docker.sock` for container management.
- `PowerDNS` (192.168.20.250) — DNS records fail if unreachable.
- `Home Assistant` (192.168.20.222) — HA automation endpoints fail if unreachable.
- `admin_api_data` volume — State mount required for SOP database.

### Soft (degrade if these are down, but service still functional)
- `prefect-server` — Metrics endpoint fails; flow triggers still work.
- `LiteLLM` (192.16