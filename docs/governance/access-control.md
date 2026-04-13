# Access Control

> **Last Updated**: 2026-03-12

## Overview

Access control is managed through Authentik SSO with role-based permissions:

- **Authentication**: OAuth2/OpenID Connect via Authentik
- **Authorization**: Group-based roles per service
- **Audit**: Access logs in Splunk

## Authentication Flow

```
User → Authentik (SSO) → OAuth token → Service validates token → Access granted
```

## User Roles

| Role | Scope | Permissions |
|------|-------|-------------|
| admin | All services | Full access, can modify configs |
| operator | Assigned services | Read + execute, no config changes |
| viewer | Assigned services | Read-only access |
| guest | Limited services | Restricted access |

## Groups

| Group | Members | Services |
|-------|---------|----------|
| homelab-admins | Todd | All services |
| ai-operators | (TBD) | AI stack only |
| media-users | Family | Plex, Overseerr |
| guests | (TBD) | Limited access |

## Service-Specific Access

### Authentik Admin Panel

- **URL**: https://auth.themillertribe-int.org/if/admin/
- **Access**: homelab-admins group only

### GitLab/GitHub

- **Authentication**: Personal access tokens (PAT)
- **Storage**: macOS Keychain (personal), OpenBao (automation)

### OpenBao

- **Admin**: Root token (1Password, break-glass only)
- **AppRole**: Service credentials (auto-generated)
- **UserPass**: Interactive admin access

### Kubernetes (if applicable)

- **RBAC**: Configured via Authentik OIDC
- **Service Accounts**: Token-based auth

## Provisioning

### Adding a New User

1. Navigate to Authentik Admin → Users
2. Click **+ Create User**
3. Set username, email, initial password
4. Assign to groups
5. Send invitation email

### Revoking Access

1. Authentik Admin → Users → Select user
2. Disable account OR remove from groups
3. Revoke active sessions
4. Rotate any personal tokens

## Audit Logging

### Access Logs Location

- **Authentik**: `index=authentik` in Splunk
- **OpenBao**: `index=security` in Splunk
- **GitLab**: `index=gitlab` in Splunk

### Common Queries

```splunk
# Failed login attempts
index=authentik "failed_login" | stats count by user, source_ip

# Privilege escalation
index=security "role_change" OR "group_add" | table _time, user, action
```

## MFA

### Requirements

- **Admin users**: MFA mandatory (TOTP or WebAuthn)
- **Standard users**: MFA recommended
- **Service accounts**: Not applicable (AppRole/JWT)

### Setup

1. User logs into Authentik
2. Navigate to **Profile** → **Devices**
3. Add TOTP app (Authy, 1Password, etc.)
4. Scan QR code, verify

## Session Management

| Setting | Value |
|---------|-------|
| Session timeout | 24 hours |
| Refresh token | 7 days |
| Concurrent sessions | 3 max |
| Idle timeout | 1 hour |
