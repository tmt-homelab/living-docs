

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance, ephemeral session state) |
| **Tolerable outage** | ≤ 5 minutes (active conversation context lost, UI shows degraded state) |
| **Blast radius if down** | `caipe-ui` healthcheck fails; all multi-agent orchestration halts; GitHub/Slack tool calls drop; LLM routing via supervisor stops |
| **Recovery time today** | Auto-restart (`unless-stopped`), ~60s startup + 60s healthcheck start_period |
| **Owner** | ? |

## What this service actually does

`caipe-supervisor` orchestrates specialized sub-agents (GitHub, Slack) via the A2A protocol. In its current single-node deployment, all agents execute in-process via MCP stdio, meaning the supervisor is the sole runtime environment for agent logic, tool invocation, and LLM routing.

The fleet uses it as the central control plane for AI-assisted workflows. `caipe-ui` connects to it over the `caipe-internal` network (`http://caipe-supervisor:8000`) to fan-out user prompts, receive streaming responses, and manage tool execution. Active conversation context, agent memory, and checkpoint state live in-process (`LANGGRAPH_CHECKPOINT_TYPE=memory`).

It is NOT a persistent state backend, NOT a distributed agent broker, and NOT a standalone LLM provider. It routes to `litellm` for model inference and relies on the `ai-mcp` network for tool server access.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-caipe/stacks/caipe/docker-compose.yml` |
| **Image** | `ghcr.io/cnoe-io/ai-platform-engineering:0.2.36` |
| **Pinning policy** | Tag-floating (`:0.2.36`); updated via CI/CD `--env-file` substitution. No digest pinning. |
| **Resource caps** | CPU: `2.0`, Memory: `3G` |
| **Volumes** | `./prompt_config.yaml:/app/prompt_config.yaml:ro`, `./prompt_config.github_agent.yaml:ro`, `./prompt_config.slack_agent.yaml:ro` (host path `/mnt/docker/stacks/caipe/`). All read-only. No state volumes. |
| **Networks** | `caipe-internal` (bridge, `172.30.40.0/24`), `ai-mcp` (external, shared with LiteLLM + 25+ MCP servers) |
| **Secrets** | CI/CD injected via `--env-file`: `LITELLM_MASTER_KEY`, `GITHUB_PAT`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `CAIPE_SESSION_SECRET` |
| **Healthcheck** | `curl -sf http://127.0.0.1:8000/.well-known/agent-card.json`. Interval: 30s, Timeout: 10s, Retries: 3, Start period: 60s |

### Configuration shape

- Runtime behavior driven entirely by environment variables. Feature flags control agent enablement (`ENABLE_GITHUB`, `ENABLE_SLACK`), tracing/RAG toggles, and OIDC middleware.
- `DISTRIBUTED_AGENTS` must be empty string for single-node mode.
- Prompt engineering configs are YAML files mounted read-only into