

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical automation) |
| **Blast radius if down** | LiteLLM cannot route browser automation tools → AI agents lose web navigation capability |
| **Recovery time today** | Auto-restart (`unless-stopped`) + Dependency wait (`playwright-backend`) |
| **Owner** | `phase-1.4-bulk-backfill` (CMDB) / MCP Fleet Maintainer |

## What this service actually does

`playwright-mcp` is a stateless MCP server proxy that exposes browser automation capabilities to the AI fleet. It authenticates incoming requests via `MCP_API_KEY`, validates them against the `admin-api`, and forwards commands to `playwright-backend`.

It does not execute browsers itself. All headless Chromium processes run in the `playwright-backend` container. `playwright-mcp` is strictly the protocol bridge between LiteLLM (MCP client) and the backend REST API.

Common confusion: It is NOT used for direct file inspection or local script execution (that is `docker-mcp` or `admin-api-mcp`). It is specifically for HTTP-based web interaction (scraping, form filling, verification).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | Build context `./playwright` (no registry tag) |
| **Pinning policy** | Build context (local repo sync required for updates) |
| **Resource caps** | None specified (Backend has `mem_limit: 2g`) |
| **Volumes** | `./shared:/app/shared:ro` (Read-only shared config) |
| **Networks** | `ai-mcp` (Internal Docker bridge) |
| **Secrets** | `services/readonly-shared/mcp_api_key`, `services/playwright/api_key` |
| **Healthcheck** | None defined (Startup blocked by `depends_on` backend health) |

### Configuration shape

Environment variables injected via `x-secrets-env` (shared across fleet) + specific overrides:
- `PLAYWRIGHT_BACKEND_URL`: `http://playwright-backend:3000` (Internal DNS)
- `PLAYWRIGHT_ALLOWED_INTERNAL_HOSTS`: Whitelist for RFC1918 access
- `ADMIN_API_URL`: `http://${DOCKP04_IP}:8000` (For auth token validation)
- `MCP_API_KEY`: Shared fleet key (validated on ingress)

No local YAML/JSON config files; all config is environment-driven at container start.

## Dependencies

