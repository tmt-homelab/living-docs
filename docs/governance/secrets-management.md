# Secrets Management

> **Last Updated**: 2026-03-12

## Overview

The homelab uses a multi-layered secrets management strategy:

1. **OpenBao** - Primary secrets backend for automation
2. **1Password Connect** - Secrets sync for Docker containers
3. **macOS Keychain** - Personal CLI credentials
4. **Environment Variables** - Runtime injection (never hardcoded)

## Secret Storage Hierarchy

| Priority | Method | Use Case |
|----------|--------|----------|
| 1 | OpenBao | Automation credentials, service tokens |
| 2 | 1Password Connect | Container secrets, Docker env vars |
| 3 | macOS Keychain | Personal CLI (git, etc.) |
| 4 | 1Password CLI | Reference/backup only |

## OpenBao Paths

| Path | Owner | Contents |
|------|-------|----------|
| `secret/stacks/ai` | AI workspace | LiteLLM, vLLM, OpenWebUI |
| `secret/stacks/automation` | Automation | GitLab PAT, Prefect, Admin API |
| `secret/stacks/core` | Core | Authentik, PostgreSQL, Redis |
| `secret/stacks/media` | Media | Plex tokens, Sabnzbd keys |
| `secret/services/*` | Various | Service-specific secrets |

## Access Patterns

### Machine-to-Machine (M2M)

**AppRole Authentication**:
```bash
ROLE_ID=$(cat ~/.config/openbao/role_id)
SECRET_ID=$(cat ~/.config/openbao/secret_id)

bao login -method=approle role_id="$ROLE_ID" secret_id="$SECRET_ID"
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
| API Keys | 90 days | `task-library/openbao-secret-rotate.md` |
| Database Passwords | 180 days | Rotate via OpenBao, update containers |
| Personal PATs | 365 days | GitLab → 1Password → OpenBao |
| TLS Certificates | Auto | Let's Encrypt (90-day renew) |

## Best Practices

### DO

- Store all secrets in OpenBao or 1Password
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
2. Retrieve "OpenBao Root Credentials"
3. Unseal vault if needed
4. Access required secret path
5. Document access in audit log

### Recovery Contacts

- **Primary**: Todd Miller (1Password admin)
- **Backup**: See 1Password "Emergency Kit"
