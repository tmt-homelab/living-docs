

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless proxy) |
| **Tolerable outage** | Hours (non-critical, `critical: false`) |
| **Blast radius if down** | LiteLLM loses access to bird sound analysis tools; AI assistants cannot identify bird calls. |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual deploy if image rebuild needed. |
| **Owner** | ? (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Provides an MCP (Model Context Protocol) interface to the BirdNET backend. It allows AI models running through LiteLLM to query bird sound analysis capabilities.

- **Primary purpose:** Translate AI requests into BirdNET API calls.
- **Consumer pattern:** HTTP API (MCP protocol) exposed to `ai-mcp` network.
- **NOT used for:** Storing audio files, managing BirdNET backend configuration, or processing raw audio locally. It is a pure proxy.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context `./birdnet`) |
| **Pinning policy** | None (local build, no digest) |
| **Resource caps** | None defined |
| **Volumes** | `./shared:/app/shared:ro` (Read-only shared config) |
| **Networks** | `ai-mcp` (Docker bridge, external) |
| **Secrets** | `ADMIN_API_TOKEN`, `OP_CONNECT_TOKEN`, `MCP_API_KEY` (via SecretsProvider) |
| **Healthcheck** | None defined |

### Configuration shape

Environment variables populated via `*secrets_env` anchor. Critical runtime var `BIRDNET_URL` points to `${DOCKP04_IP}:8080`. Secrets fetched at startup via `SecretsProvider` (Admin API -> 1Password Connect fallback).

## Dependencies

### Hard (service cannot start or operate without these)
- **SecretsProvider** — Fails startup if `MCP_API_KEY` cannot be resolved.
- **BirdNET Backend** — `http://${DOCKP04_IP}:8080`. MCP tools fail if backend is unreachable.
- **`ai-mcp` Network** — Required for LiteLLM communication.

### Soft (degrade if these are down, but service still functional)
- **Admin API** — Used for secret rotation/lookup; service may fallback to cached env vars if available.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes AI requests to this MCP server. Breakage causes tool invocation failures.

## State & persistence

- **Database tables**: None.
- **Filesystem state**: None writable. `./shared` volume is read-only (`:ro`).
- **In-memory state**: Request context only