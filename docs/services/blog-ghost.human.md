

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 24 hours (non-critical) |
| **Blast radius if down** | Public blog (`overlabbed.com`) inaccessible. Email notifications (Mailgun) fail. No internal fleet impact. |
| **Recovery time today** | Auto-restart (container only) / Manual (data restore if corruption) |
| **Owner** | ? (CMDB registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Hosts the public-facing Ghost CMS at `overlabbed.com`. Persists content (posts, pages, images) in an embedded MySQL 8 instance and filesystem volumes. Exposes traffic via Cloudflare Tunnel (no public inbound ports).

Other fleet services do not consume data from this service. It is a public endpoint only. It is NOT used for internal documentation, API gateway functions, or shared media storage for other homelab services.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-media/stacks/blog/docker-compose.yml` |
| **Image** | `ghost:5-alpine`, `mysql:8.0`, `cloudflare/cloudflared:latest` |
| **Pinning policy** | Tag-floating (`5-alpine`, `8.0`, `latest`). **Risk:** `cloudflared:latest` unpinned. |
| **Resource caps** | ? (No limits defined in compose) |
| **Volumes** | `blog_ghost_content` (named), `blog_mysql_data` (named), `/mnt/docker/blog-data/themes/...` (bind mount) |
| **Networks** | `blog-internal` (internal), `infra-services` (external) |
| **Secrets** | ? (Env vars `${GHOST_DB_PASSWORD}`, `${MAILGUN_SMTP_PASSWORD}`, `${CF_TUNNEL_TOKEN_BLOG}`) |
| **Healthcheck** | Defined. Ghost: Admin API spider check. MySQL: `mysqladmin ping`. Cloudflared: Metrics ready check. |

### Configuration shape

Ghost environment variables dictate database connection, site URL, and Mailgun SMTP settings. MySQL uses env vars for schema initialization and creds. Cloudflared uses a mounted YAML config (`config.yml`) and a tunnel token. No external config files for Ghost itself; all config via env.

## Dependencies

### Hard (service cannot start or operate without these)
- `blog-mysql` — Internal container. Ghost fails to start without DB connection.
- Cloudflare Tunnel — External dependency. If CF token invalid or tunnel offline, site is unreachable from internet.

### Soft (degrade if these are down, but service still functional)
- Mailgun — Email notifications fail, but site remains readable/writable.

### Reverse (services that depend on THIS service)
- None. (Public-facing only).

## State & persistence

**Critical for reliability design.** State is local to host `tmtdockp04` and not shared.

- **Database tables / schemas:** `ghost` DB in `blog_mysql_data` volume. Contains posts, users, settings. Growth rate: Low (<1GB/year).
- **Filesystem state:** `blog_ghost_content` volume contains uploads (images, PDFs). Bind mount `/mnt/docker/blog-data/themes` contains theme code.
- **In-memory state:** Ghost session cache, Node.js heap. Lost on restart (ephemeral).
- **External state:** None (CF Tunnel tokens stored in env, not persisted locally).
- **Backups:** ? (No backup policy visible in compose or CMDB).
- **RPO/RTO:** ? (Unknown backup frequency or restore procedure).

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | <5% (Idle) | >80% sustained | Throttles requests |
| Memory | ~512MB | >90