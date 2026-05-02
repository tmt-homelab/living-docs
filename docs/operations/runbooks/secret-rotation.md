# Secret Rotation Runbook

> **Purpose**: Rotate API keys, tokens, and passwords
> **Severity**: P2 - Service Degraded (if done incorrectly)
> **Agent**: Changemaker

## Prerequisites

- Access to 1Password Connect (via Admin API or direct)
- Access to 1Password (for break-glass)
- GitLab/GitHub PAT for committing changes
- Understanding of consuming services

## Rotation Procedure

### Step 1: Identify Consuming Services

```bash
# Find containers using the secret
grep -r "SECRET_NAME" /mnt/docker/stacks/*/docker-compose.yml
```

### Step 2: Generate New Secret

**Via 1Password Connect**:
```bash
# Read current secret first
curl -s "http://localhost:8080/v1/vaults/Homelab/items/<item-id>" \
  -H "Authorization: Bearer $OP_CONNECT_TOKEN"


# Update via Admin API
curl -s -X PATCH "https://admin-api.themillertribe-int.org/secrets/stacks/<service>" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"api_key":"new-generated-key"}}'
```

**Via Admin API**:
```bash
ADMIN_API_TOKEN=$(security find-generic-password -s admin-api.themillertribe-int.org -a claude-admin-api-token -w)

curl -s -X PATCH "https://admin-api.themillertribe-int.org/secrets/stacks/<service>" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"api_key":"new-generated-key"}}'
```

**⚠️ CRITICAL**: Use PATCH (merge), NOT POST (replace)

### Step 3: Update GitOps Repository

```bash
cd ~/Documents/Claude/repos/homelab-gitops
git checkout -b feature/NNN-secret-rotation-<service>

# Update .env.template (NOT .env - secrets go in 1Password Connect)
# Update docker-compose.yml environment variables to reference new secret path

git add stacks/<service>/
git commit -m "feat(project-NN): rotate <service> secret

Rotated API key for <service>. New secret stored in 1Password Connect at Homelab/stacks/<service>.

Risk: Contained / Easy / AUTO"

git push -u origin feature/NNN-secret-rotation-<service>
```

### Step 4: Create Merge Request

Include in MR description:
- Secret rotated: `<service>`
- New secret path: `secret/stacks/<service>`
- Affected containers: `<list>`
- Rollback: Revert MR, restore old secret from 1Password Connect version history

### Step 5: Deploy

After Todd merges:
```bash
# CI/CD auto-deploys
# Verify container restarted with new secret
sudo docker logs <container> --tail 20 | grep -i "authenticated\|connected"
```

### Step 6: Revoke Old Secret

**Via 1Password Connect**:
```bash
# Mark old version as inactive via Admin API
curl -s -X DELETE "https://admin-api.themillertribe-int.org/secrets/stacks/<service>/versions/<version>" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN"
```

## Rotation Schedule

| Secret Type | Frequency | Owner |
|-------------|-----------|-------|
| API Keys | 90 days | Workspace owner |
| Database Passwords | 180 days | Core workspace |
| Personal PATs | 365 days | Todd |
| TLS Certificates | Auto (90 days) | Let's Encrypt |

## Emergency Rotation

**Trigger**: Secret suspected compromise

**Immediate Actions**:
1. Rotate secret in 1Password Connect (Step 2)
2. Deploy ASAP (skip Advocate challenge for P1)
3. Revoke old secret immediately
4. Investigate compromise vector
5. Document in incident report

## Rollback Procedure

```bash
# Restore old secret from 1Password Connect version history
# Via Admin API
curl -s "https://admin-api.themillertribe-int.org/secrets/stacks/<service>" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" | jq '.data'

# Revert MR
git checkout <commit-before-rotation>
git push

# Redeploy
sudo docker compose -f stacks/<service>/docker-compose.yml up -d
```
