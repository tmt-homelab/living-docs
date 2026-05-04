

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (Non-critical per CMDB) |
| **Blast radius if down** | LiteLLM stops routing GitHub tool calls → AI assistants cannot manage repos/issues |
| **Recovery time today** | Auto-restart (`unless-stopped`) |
| **Owner** | ? |

## What this service actually does

GitHub MCP server exposes GitHub API capabilities to the AI fleet via the Model Context Protocol. It allows LLMs to read/write repositories, manage issues, and trigger workflows securely.

- **Primary purpose:** Bridge between AI agents and GitHub.com/GitHub Enterprise.
- **Consumer pattern:** HTTP API via `ai-mcp` network. LiteLLM acts as the sole gateway; direct access from outside `ai-mcp` is blocked.
- **Not used for:** Hosting Git repositories (it consumes GitHub's API), general CI/CD execution (Prefect/Splunk handle orchestration/logging).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/mcp-servers/docker-compose.yml` |
| **Image** | `local-build` (context: `./github`) |
| **Pinning policy** | None (local build, no upstream digest) |
| **Resource caps** | ? (None defined in compose) |
| **Volumes** | `./shared:/app/shared:ro` (read-only config share) |
| **Networks** | `ai-mcp` (external, isolated) |
| **Secrets** | `services/github-mcp/mcp_api_key`, `services/github/pat` (via SecretsProvider) |
| **Healthcheck** | ? (None defined in compose) |

### Configuration shape

Environment variables injected via `x-secrets-env` and specific overrides. Secrets fetched at startup via `SecretsProvider().get_secret(path)`. Key env vars include `GITHUB_DEFAULT_ORG` and `MCP_API_KEY`. Configuration is ephemeral; all persistence is in GitHub's cloud API.

## Dependencies

### Hard (service cannot start or operate without these)
- **SecretsProvider (Admin API / 1Password)** — Required for `MCP_API_KEY` and `GITHUB_TOKEN`. Service fails to auth if secrets unavailable.
- **LiteLLM Gateway** — Required for network reachability (`ai-mcp` isolation).
- **GitHub API** — External dependency. Rate limits apply.

### Soft (degrade if these are down, but service still functional)
- **None** — Service runs but cannot function without GitHub API access.

### Reverse (services that depend on THIS service)
- **AI Assistants (via LiteLLM)** — Rely on this for repo management. Breakage prevents code changes by AI.

## State & persistence

- **Database tables / schemas:** None.
- **Filesystem state:** None. `./shared` volume is read-only.
- **In-memory state:** API sessions cleared on restart.
- **External state:** All state resides in GitHub.com.
- **Backup strategy:** Not applicable (stateless).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ? | ? | ? |
| Memory | ? | ? | ? |
| Disk I/O | Minimal (logs only) | ? | ? |
| Network | ? | ? | ? |
| GPU | N/A | N/A | N/A |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom:** LiteLLM returns 503/504 on GitHub tool calls.
  - **Root cause:** SecretsProvider unreachable or GitHub API rate limit hit.
  - **Mitigation:** Check `SecretsProvider` status. Verify GitHub rate limits.
  - **Prevention:** Implement token caching or rate limit awareness in MCP client.

- **Symptom:** Container exits immediately.
  - **Root cause:** Missing `GITHUB_TOKEN` or `MCP_API_KEY`.
  - **Mitigation:** Verify 1Password Connect / Admin API connectivity on `tmtdockp01`.
  - **Prevention:** Add startup probe for secret validation.

- **Symptom:** Network timeout.
  - **Root cause:** `ai-mcp` network misconfiguration or host firewall.
  - **Mitigation:** Verify Docker network `ai-mcp` exists and LiteLLM is reachable.
  - **Prevention:** Network policy enforcement in compose.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless). Multiple instances possible behind a load balancer.
- **Coordination requirements** None. No leader election needed.
- **State sharing across replicas** None. All state external (GitHub).
- **Hardware bindings** None. No USB/GPU/Kernel module dependencies.
- **Network constraints** 
  - Must reside on `ai-mcp` network. 
  - Cannot communicate on `host` network directly.
  - Out