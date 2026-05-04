

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (UI only; backend logic continues) |
| **Blast radius if down** | Users lose chat interface access. `caipe-supervisor` remains operational for CLI/API consumers. |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual restart if env config invalid |
| **Owner** | ? (Phase 1.4 automation) |

## What this service actually does

Serves the Next.js chat interface for the CAIPE multi-agent system. It acts as a thin client wrapper, connecting user input to the `caipe-supervisor` via the A2A protocol. It handles authentication (NextAuth/OIDC) and session management.

The fleet uses it as the primary human entry point. It is NOT a compute node (LLM inference happens at `litellm`), NOT a database (Mongo disabled), and NOT an agent orchestrator (handled by `caipe-supervisor`).

When it's broken, users see 502/504 errors from Caddy or "Agent Unavailable" messages in the chat window. Supervisor logs remain clean.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-caipe/stacks/caipe/docker-compose.yml` |
| **Image** | `ghcr.io/cnoe-io/caipe-ui:0.2.36` |
| **Pinning policy** | Tag-floating (`0.2.36`); no digest pinning in compose |
| **Resource caps** | 512M memory, 0.5 CPU |
| **Volumes** | None (stateless container) |
| **Networks** | `caipe-internal` (backend), `ai-services` (ingress via Caddy) |
| **Secrets** | Injected via CI/CD process substitution (`${VAR}`) at runtime |
| **Healthcheck** | `GET http://127.0.0.1:3000/api/health` (15s interval, 5s timeout) |

### Configuration shape

Configuration is purely environment-driven. `NEXT_PUBLIC_` vars control client-side features (RAG, Mongo, SSO). Server-side vars (OIDC secrets) are required for auth handshake. No `yaml` config files mounted; all state driven by Env.

## Dependencies

### Hard
- `caipe-supervisor` — A2A backend. UI fails to load chat context if supervisor is unhealthy.
- `ai-services` network — Required for Caddy proxy to reach container on port 3000.

### Soft
- `litellm` — Indirectly via supervisor. If LiteLLM is down, UI shows "Agent Error" but remains responsive.

### Reverse
- None (Terminal service).

## State & persistence

**Zero persistent state.**

- **Database tables / schemas:** None (`NEXT_PUBLIC_MONGODB_ENABLED=false`).
- **Filesystem state:** None (container writable layer ephemeral).
- **In-memory state:** 
  - NextAuth session tokens (stored in HTTP-only cookies).
  - Chat context window (lost on refresh/restart).
- **External state:** None.
- **Persistence implications:** Restarting the container does not lose user sessions (cookies are browser-side), but active chat threads are lost if they were server-side tracked (currently disabled).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 5-10% (static asset serving) | > 80% sustained | Degraded UI load times |
| Memory | 150-250M | > 450M | OOM kill (limit 512M) |
| Disk I/O | Negligible | N/A | N/A |
| Network | < 10KB/s | > 1MB/s sustained | Connection timeouts |
| Request latency p50 | < 50ms | > 500ms | 504 Gateway Timeout |
| Request rate | < 10 RPS | > 50 RPS | Thread pool exhaustion |

## Failure modes

- **Symptom:** Caddy logs 502 Bad Gateway.
  - **Root cause:** `caipe-ui` container unhealthy or network isolation failure.
  - **Mitigation:** `docker restart caipe-ui`.
  - **Prevention:** Healthcheck monitoring.

- **Symptom:** "Authentication Failed" loop on login.
  - **Root cause:** OIDC env vars mismatch (Phase 3 config drift) or `NEXTAUTH_SECRET` mismatch across replicas.
  - **Mitigation:** Verify `OIDC_CLIENT_ID` and `NEXTAUTH_SECRET` consistency.
  - **Prevention:** Config validation in CI.

- **Symptom:** Chat messages fail to send.
  - **Root cause:** `caipe-supervisor` unreachable via `caipe-internal` network.
  - **Mitigation:** Check supervisor health.
  - **Prevention:** Network policy enforcement.

## HA constraints (input to fleet-reliability design)

- **Replicable?** Yes (stateless), but with session caveats.
- **Coordination requirements:** None.
- **State sharing across replicas:** 
  - **Critical:** `NEXTAUTH_SECRET` MUST be identical across all replicas for shared session cookies to work.
  - **Critical:** MongoDB is disabled. If enabled, DB must be shared external.
  - **Session Stickiness:** Not configured. Load balancer must support sticky sessions OR `NEXTAUTH_SECRET` must be shared secret (current default supports this if secret is consistent).
- **Hardware bindings:** None.
- **Network constraints:** 
  - Must be attached to `caipe-internal` (subnet 172.30.40.0/24) to resolve `caipe-supervisor`.
  - Must be attached to `ai-services` for Caddy ingress.
- **Cluster size constraints:** None (single-instance mode currently).
- **Migration cost:** Low. Scaling requires externalizing `NEXTAUTH_SECRET` and ensuring OIDC issuer consistency.

## Operational history

### Recent incidents (last 90 days)
- None recorded (service provisioned 2026-05-03).

### Recurring drift / chronic issues
- N/A.

### Known sharp edges
- **SSO Toggle:** `ALLOW_DEV_ADMIN_WHEN_SSO_DISABLED=true` allows bypass. Security risk if OIDC is intended.
- **Network DNS:** Container relies on Docker DNS for `caipe-supervisor`. If `caipe-internal` network is recreated, DNS may stale until restart.

## Open questions for Architect

- ? Should `NEXTAUTH_SECRET` be managed by external secret store (e.g., Vault) to ensure consistent HA scaling?
- ? When Phase 3 (OIDC) activates, does `caipe-ui` require read-only access to Hydra JWKS URI (`https://hydra.themillertribe-int.org/.well-known/jwks.json`)?
- ? Does `caipe-supervisor` need to expose a public endpoint for UI if `caipe-internal` network is isolated from `ai-services`?

## Reference

- Compose: `homelab-caipe/stacks/caipe/docker-compose.yml`
- Logs: `/var/lib/docker/containers/caipe-ui/caipe-ui-json.log` (json-file, 50m max)
- Dashboards: N/A (Phase 1)
- Runbooks: N/A
- Upstream docs: `https://github.com/cnoe-io/ai-platform-engineering`
- Related services: [`caipe-supervisor`](