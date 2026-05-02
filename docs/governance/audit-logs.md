# Audit Logs

> **Last Updated**: 2026-03-12

## Overview

Audit logs provide tamper-evident records of all security-relevant events:

- Authentication events (login, logout, MFA)
- Authorization changes (role assignments, group membership)
- Secret access (reads, writes, rotations)
- Configuration changes (infrastructure modifications)

## Log Sources

| Source | Index | Retention |
|--------|-------|-----------|
| Authentik | `authentik` | 90 days |
| 1Password Connect | `security` | 90 days |
| GitLab/GitHub | `gitlab` | 90 days |
| Docker | `docker` | 30 days |
| Admin API | `admin` | 90 days |

## Common Audit Queries

### Authentication Events

```splunk
index=authentik (login OR logout OR failed_login) | timechart span=1h count by user
```

### Secret Access

```splunk
index=security index="secret/stacks/ai" | table _time, entity, path, method
```

### Configuration Changes

```splunk
index=admin action="config_change" | sort -_time
```

### Privilege Escalation

```splunk
index=security (role_change OR group_add OR permission_grant)
  | table _time, user, target, action, source_ip
```

## Alert Rules

### Suspicious Activity

| Trigger | Action |
|---------|--------|
| 5+ failed logins in 5 min | P2 alert to #homelab-alerts |
| Secret access outside business hours | P2 alert to #homelab-alerts |
| Privilege escalation | P1 alert to Todd DM |
| Multiple group joins in 1 hour | P3 daily digest |

### Alert Configuration

**Splunk Alerts**:
- Navigate to **Settings** → **Alerts**
- Create new alert with search query
- Set trigger conditions
- Configure notification actions

## Compliance

### Data Retention

| Log Type | Retention | Archive |
|----------|-----------|---------|
| Authentication | 90 days | None |
| Secret Access | 90 days | None |
| Configuration | 90 days | None |
| Security Events | 90 days | None |

### Audit Export

```bash
# Export audit logs for compliance review
curl -s "https://splunk.themillertribe-int.org:8089/services/search/jobs/export" \
  -u admin:$SPLUNK_PASSWORD \
  --data "search=index=security earliest=-90d@h latest=now | outputcsv" \
  > /tmp/audit_export_$(date +%Y%m%d).csv
```

## Regular Reviews

### Weekly

- Failed login attempts
- New user additions
- Secret access anomalies

### Monthly

- Full access review (all users, all groups)
- Stale account cleanup
- Token rotation verification

### Quarterly

- Comprehensive audit log review
- Policy compliance check
- Access control matrix update

## Incident Correlation

### Security Incident Investigation

1. Identify time range and affected services
2. Pull relevant logs from Splunk
3. Correlate across log sources
4. Document timeline in incident report

### Example Investigation Query

```splunk
index=(authentik OR security OR admin) user="suspected_user"
  | sort _time
  | table _time, index, user, action, source_ip, details
```
