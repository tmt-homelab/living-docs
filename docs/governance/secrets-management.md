# Secrets Management

> **Last Updated**: 2026-03-12

## Overview

The homelab uses a multi-layered secrets management strategy:

1. **1Password Connect** - Primary secrets backend for Docker containers
2. **1Password CLI** - Reference and backup
3. **macOS Keychain** - Personal CLI credentials
4. **Environment Variables** - Runtime injection (never hardcoded)

## Secret Storage Hierarchy

| Priority | Method | Use Case |
|----------|--------|----------|
| 1 | 1Password Connect | Container secrets, Docker env vars |
| 2 | 1Password CLI | Reference/backup only |
| 3 | macOS Keychain | Personal CLI (git, etc.) |
| 4 | 1Password CLI | Reference/backup only |

## 1Password Connect Paths

| Path | Owner | Contents |
|------|-------|----------|
| `Homelab/stacks/ai` | AI workspace | LiteLLM, vLLM, OpenWebUI |
| `Homelab/stacks/automation` | Automation | GitLab PAT, Prefect, Admin API |
| `Homelab/stacks/core` | Core | Authentik, PostgreSQL, Redis |
| `Homelab/stacks/media` | Media | Plex tokens, Sabnzbd keys |
| `Homelab/services/*` | Various | Service-specific secrets |

## Access Patterns

### Machine-to-Machine (M2M)

**1Password Connect**:
```bash
# Read secret via 1Password Connect API
curl -s "http://localhost:8080/v1/vaults/Homelab/items/<item-id>" \
  -H "Authorization: Bearer $OP_CONNECT_TOKEN"
```

### Container Injection

Via 1Password Connect:
```yaml
environment:
  - API_KEY=1password://Homelab/service/api_key
```

### Admin API (Break-Glass)

```bash
ADMIN_API_TOKEN=$(security find-generic-password -s admin-api.themillertribe-int.org -a claude-admin-api-token -w)

curl -s "https://admin-api.themillertribe-int.org/secrets/stacks/ai" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN"
```

## Rotation Policy

| Secret Type | Rotation Frequency | Procedure |
|-------------|-------------------|-----------|
| API Keys | 90 days | Rotate via Admin API, update 1Password |
| Database Passwords | 180 days | Rotate via 1Password Connect, update containers |
| Personal PATs | 365 days | GitLab → 1Password |
| TLS Certificates | Auto | Let's Encrypt (90-day renew) |

## Best Practices

### DO

- Store all secrets in 1Password Connect
- Use environment variable injection at runtime
- Rotate secrets on schedule
- Audit access logs regularly
- Use least-privilege policies

### DON'T

- Hardcode secrets in compose files
- Commit `.env` files to git
- Share secrets via chat/email
- Use the same secret across services
- Store secrets in container writable layers

## Emergency Access

### Break-Glass Procedure

1. Access 1Password (macOS Keychain)
2. Retrieve "Admin API Credentials"
3. Access required secret path via Admin API
5. Document access in audit log

### Recovery Contacts

- **Primary**: Todd Miller (1Password admin)
- **Backup**: See 1Password "Emergency Kit"
