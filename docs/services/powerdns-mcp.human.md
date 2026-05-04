

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical, CMDB `critical: false`) |
| **Blast radius if down** | LiteLLM loses DNS management capability → AI assistants cannot query/update PowerDNS records |
| **Recovery time today** | Auto-restart (`unless-stopped`), manual intervention if secrets fetch fails |
| **Owner** | `?` (CMDB registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

`powerdns-mcp` is an MCP server that exposes the PowerDNS Authoritative Server API to the homelab AI fleet. It allows LLMs to manage DNS records (A, AAAA, CNAME, etc.) via natural language.

Other fleet services (specifically `LiteLLM` gateway) reach this service via the `ai-mcp` Docker network. It acts as a thin HTTP client wrapper; it does not resolve DNS queries itself. It is NOT used for authoritative DNS serving—that role belongs to the upstream PowerDNS backend at `DNS_PRIMARY_IP:8081`. When this service is down, AI agents can still resolve hostnames via the network's standard resolver, but they cannot automate record creation or updates.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context: `./powerdns`) |
| **Pinning policy** | None (local build; no digest/tag in compose) |
| **Resource caps** | None (no mem_limit/CPU set in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config share) |
| **Networks** | `ai-mcp` (external bridge) |
| **Secrets** | 1Password Connect: `services/powerdns-mcp/mcp_api_key`, `services/powerdns/api_key` |
| **Healthcheck** | None defined in compose |

### Configuration shape

Configuration is driven by environment variables injected at runtime via `SecretsProvider` (Python module).
- **Core Env:** `PDNS_API_URL` (set via `${DNS_PRIMARY_IP}:8081`).
- **Auth:** `MCP_API_KEY` (validated against incoming requests), `PDNS_API_KEY` (used to talk upstream).
- **Secrets Provider:** Fetches secrets from 1Password Connect or Admin API at startup. If `ADMIN_API_TOKEN` is unavailable, falls back to direct OP Connect.

## Dependencies

### Hard (service cannot start or operate without these)
- **`ai-mcp` network** — Docker bridge isolation; LiteLLM routes traffic here.
- **`DNS_PRIMARY_IP`** — External PowerDNS backend address (env var resolved at deploy time).
- **Admin API (dockp04)** — Hosted at `http://${DOCKP04_IP}:8000`; required for secret fetching fallback.
- **1Password Connect** — Source of truth for `PDNS_API_KEY` and `MCP_API_KEY`.

### Soft (degrade if these are down, but service still functional)
- **None** — All dependencies are hard for operational connectivity.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes MCP requests from AI models to this container.
- **AI Assistants** — Indirect dependency; they lose DNS management tools if this service is down.

## State & persistence

This service is designed to be stateless.
- **Database tables / schemas:** None (no local DB).
- **Filesystem state:** None writable. `./shared` volume is mounted read-only (`:ro`).
- **In-memory state:** Runtime token caches cleared on container restart.
- **External state:** All DNS state lives in the upstream PowerDNS backend (host `tmtdockp01` or `dockp01`).
- **Backups:** Container state requires no backup. Secrets are managed by 1Password.

## Behavior baselines

| Metric