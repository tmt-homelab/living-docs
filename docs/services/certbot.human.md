

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | 90 days (cert validity); Renewal window failure = 12h max delay |
| **Blast radius if down** | TLS termination fails on `tmtdockp01` proxy. `caddy` continues serving stale certs until expiry. External access to `*.themillertribe-int.org` breaks on expiry. |
| **Recovery time today** | Auto-restart (`unless-stopped`); Manual intervention required if DNS API key rotated or cert state corrupted. |
| **Owner** | ? |

## What this service actually does

Provisions and renews TLS certificates for `*.themillertribe-int.org` and `themillertribe-int.org` using Cloudflare DNS-01 challenge. It generates ACME certificates and stores them in a named volume shared with the `caddy` reverse proxy.

Consumers: `caddy` (reads `/etc/letsencrypt` volume mount for TLS handshake).
Not used for: HTTP reverse proxying, load balancing, or DNS record management (only triggers API updates for challenge validation).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp01-proxy/docker-compose.yml` |
| **Image** | `certbot/dns-cloudflare:latest` |
| **Pinning