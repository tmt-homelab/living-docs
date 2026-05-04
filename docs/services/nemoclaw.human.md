

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | "Hours" (critical=false, ops triage degraded) |
| **Blast radius if down** | AI ops triage stops, playbook automation stalls, Splunk dashboard loses live data ingestion. Admin API metrics degrade. |
| **Recovery time today** | Auto-restart (`on-failure`), manual DB restore if corruption. |
| **Owner** | Todd Miller (tmiller) |

## What this service actually does

NemoClaw is the fleet's AI-driven operations brain. It ingests incident data (Splunk, alerts), dispatches LLM models (via LiteLLM), and executes remediation playbooks via the Admin API. It connects to Home Assistant and PowerDNS for state changes. It is NOT a general-purpose chatbot; it is a specific automation agent with audit trails.

When broken, the Admin API cannot trigger AI remediation, and the "Tier-1 ops-brain" triage path (shadow mode) stops logging decisions to the Splunk dashboard.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-automation/stacks/dockp04-automation/docker-compose.yml` |
| **Image** | `nemoclaw:latest` (Built from `Dockerfile` in stack) |
| **Pinning policy** | Tag-floating (`latest` — rebuilds on deploy) |
| **Resource caps** | `memory: 1G`, `cpus: '2.0'` |
| **Volumes** | `/mnt/docker/backups` (ro), `nemoclaw_audit` (rw, audit logs) |
| **Networks** | `infra-services`, `automation`, `db-nemoclaw` |
| **Secrets** | Env vars injected at deploy (DB password, OIDC creds, API keys) |
| **Healthcheck** | `curl -f http://127.0.0.1:8100/health` (30s interval, 3 retries) |

### Configuration shape

Environment-driven. Key toggles: `NEMOCLAW_REQUIRE_AUTH` (auth enforcement), `NEMOCLAW_F048_4B_ENABLED` (canary watch). Connects to external Ops Brain (`192.168.20.16`), LiteLLM (`192.168.20.15`), and local `admin-api`.

## Dependencies

### Hard (service cannot start or operate without these)
- `nemoclaw-postgres` — Stores run state, audit records, and config. If down, service fails healthcheck.
- `admin-api` — Control plane for playbooks.
- `hydra` (OIDC) — Authentication token issuance (Corvus integration).

### Soft (degrade if these are down, but service still functional)
- `liteLLM` (`192.168.20.15`) — AI classification fails, falls back to rules.
- `ops-brain` (`192.168.20.16`) — Tier-1 triage shadow mode stops.
- `splunk` — Audit ingestion drops (buffering may occur).

### Reverse (services that depend on THIS service)
- `admin-api` — Calls NemoClaw for `/prefect/*` routes and AI analysis.
- `prefect-worker` — May trigger flows via NemoClaw (indirectly via Admin API).

## State & persistence

- **Database:** `nemoclaw-postgres` (Postgres 16-alpine). Schema unknown (managed by app migrations).
- **Filesystem:** `nemoclaw_audit` volume (`/data/audit.jsonl`). Growing append-only log.
- **In-memory:** Runtime state lost on restart (stateless app logic).
-