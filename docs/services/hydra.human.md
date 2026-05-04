

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Minutes (auth control plane); prolonged outage blocks all OIDC flows |
| **Blast radius if down** | Corvus, sentinel-probe, nemoclaw, sync-docs, pi-broker, cc-<host> fail auth checks. New logins blocked. |
| **Recovery time today** | Auto-restart (container); Manual (SQLite corruption/secret rotation) |
| **Owner** | `?` (human); `phase-1.4-rebase-2026-05-03` (agent/record) |

## What this service actually does

Ory Hydra OIDC/OAuth2 issuer for the homelab Phase 2 stack. Issues JWT access tokens (RS256) for m2m clients and browser OIDC flows. Stores client credentials, consent sessions, and token metadata in a local SQLite database.

Fleet services (Corvus, pi-broker, etc.) authenticate via `client_credentials` flow against this service. Tokens carry native `scope` claims used by Corvus for authorization decisions (design v2.2 §3.4).

It is NOT a user directory (user login UI is external at `login.themillertribe.org`). It is NOT a secrets store (though it manages signing keys); it relies on 1Password for initial secret injection. It does NOT handle TLS termination (Caddy terminates TLS; Hydra speaks HTTP internally).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-core/stacks/hydra/docker-compose.yml` |
| **Runtime path** | `/mnt/docker/stacks/hydra/` on `tmtdockp04` |
| **Image** | `oryd/hydra:v2.3.0` |
| **Pinning policy** | Tag `v2.3.0` (last v2.x); config schema verified against v2.2 spec |
| **Resource caps** | Unknown (not defined in compose) |
| **Volumes** | `/mnt/docker/stacks/hydra/data` (SQLite state, critical), `./hydra.yml` (config) |
| **Networks** | `infra-services` (external Docker network, shared with Caddy) |
| **Secrets** | `op://Homelab/homelab-hydra-system-secret/credential`, `op://Homelab/homelab-hydra-cookie-secret/credential` |
| **Healthcheck** | `GET /health/ready` on `127.0.0.1:4444` (30s interval, 5s timeout) |

### Configuration shape

Configuration is split between environment variables (secrets, URLs, TTLs) and a mounted YAML file (`hydra.yml`). `SECRETS_SYSTEM` is the critical signing key; rotation invalidates all existing tokens. `URLS_SELF_ISSUER` must match the public URL advertised to clients. Admin port (4445) is not exposed; management via `docker compose exec`.

## Dependencies

### Hard (service cannot start or operate without these)
- **1Password Connect** — injects `SECRETS_SYSTEM` and `SECRETS_COOKIE`. Service fails to start if env vars are missing.
- **SQLite File** — `/mnt/docker/stacks/hydra/data/hydra.sqlite`. Corruption halts all auth operations.
- **Caddy** — Hydra only listens on internal HTTP (4444). External access requires Caddy proxy.

### Soft (degrade if these are down, but service still functional)
- None. Service is self-contained regarding data storage.

### Reverse (services that depend on THIS service)
- **Corvus** — reads token `scope` claims for routing/auth. Breaks immediately if Hydra is down.
- **sentinel-probe / pi-broker** — use `client_credentials` for m2m auth. Services lose network access/auth.
- **login.themillertribe.org** — OIDC flow termination (consent/login UI) relies on Hydra for token minting.

## State & persistence

- **Database:** SQLite single file (`hydra.sqlite`). No WAL mode explicitly forced in compose (default