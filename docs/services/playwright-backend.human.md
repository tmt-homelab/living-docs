

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | "minutes" (Non-critical automation, `critical: false` in CMDB) |
| **Blast radius if down** | `playwright-mcp` fails healthcheck → LiteLLM cannot execute browser automation tools → AI assistants lose web access capabilities |
| **Recovery time today** | `auto-restart` (`unless-stopped` policy) |
| **Owner** | `?` (CMDB `registered_by`: `phase-1.4-bulk-backfill`) |

## What this service actually does

Headless Chromium REST API backend for browser automation. It accepts requests from `playwright-mcp` to render pages, scrape content, or interact with DOM elements. The fleet uses it as the execution engine for AI-driven web tasks.

When it's broken, `playwright-mcp` cannot establish a connection to the browser engine, causing any LLM tool use involving web browsing to timeout or fail immediately. It is NOT used for direct user access or general HTTP proxying; traffic is strictly proxied via `playwright-mcp` → `playwright-backend`.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context: `./playwright-backend`) |
| **Pinning policy** | `none` (Rebuilds on `up --build`; no digest/tag lock visible in inputs) |
| **Resource caps** | `mem_limit: 2g`; No CPU limit defined |
| **Volumes** | `./shared:/app/shared:ro` (Read-only shared volume) |
| **Networks** | `ai-mcp` (Internal API), `ai-services` (Egress/Browser access) |
| **Secrets** | `services/playwright/api_key` (via SecretsProvider) |
| **Healthcheck** | `undefined` (Critical: `playwright-mcp` depends on `service_healthy`, but this service lacks a `healthcheck` block in compose) |

### Configuration shape

Environment variables injected via `*secrets_env` block plus service-specific overrides.
- `MAX_BROWSERS`: Limits concurrent browser instances (Default: `3`).
- `IDLE_TIMEOUT_MS`: Browser instance expiration (Default: `600000` ms).
- `ALLOWED_INTERNAL_HOSTS`: Whitelist for RFC1918 access (Default: empty).
- Secrets resolved at startup via `SecretsProvider` (Admin API first, 1Password fallback).

## Dependencies

### Hard (service cannot start or operate without these)
- **Network Egress (`ai-services`)**: Browser instances require outbound internet access to render external pages. Blocking this network isolates the browser.
- **Secrets Provider**: Required to fetch `PLAYWRIGHT_API_KEY`. Startup fails if secrets resolution times out (unless env fallback exists).

### Soft (degrade if these are down, but service still functional)
- None recorded.

### Reverse (services that depend on THIS service)
- **