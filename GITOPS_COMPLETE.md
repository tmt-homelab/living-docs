# GitOps Implementation Complete

> **Date**: 2026-04-13  
> **Pattern**: GitOps Pattern 2 (Git-to-Git)  
> **Status**: ✅ Code Complete, ⏳ Manual Setup Required

---

## What Changed

### Before (Not GitOps ❌)
- SSH-based deployment (`appleboy/ssh-action`)
- Manual SSH key generation
- GitHub Secrets for runtime secrets
- Imperative scripts (`setup_docs_stack.sh`)
- No reconciliation loop

### After (GitOps ✅)
- Git-to-Git deployment (living-docs → homelab-gitops)
- Declarative configuration (docker-compose.yml)
- 1Password Connect for runtime secrets
- Reconciliation loop (`gitops-sync.sh`)
- All state in Git, rollback via `git revert`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  living-docs repo                                           │
│  - MkDocs source (markdown)                                 │
│  - GitHub Actions: Build → Push to homelab-gitops          │
└────────────────────────┬────────────────────────────────────┘
                         │ (git push to homelab-gitops)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  homelab-gitops repo                                        │
│  - stacks/core/docs/site/  ← Built site (committed)         │
│  - stacks/core/docs/docker-compose.yml                      │
└────────────────────────┬────────────────────────────────────┘
                         │ (git pull + restart)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  dockp04                                                    │
│  - gitops-sync.sh (cron or manual)                          │
│  - docker compose up -d                                     │
│  - 1Password Connect for secrets                            │
│  - Caddy → docs.themillertribe-int.org                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Created/Modified

### living-docs repo
- ✅ `.github/workflows/sync-docs.yml` - GitOps deployment workflow
- ✅ `PROJECT_CONTEXT.md` - Updated for GitOps

### homelab-gitops repo
- ✅ `stacks/core/docs/docker-compose.yml` - Container config
- ✅ `stacks/core/docs/gitops-sync.sh` - Reconciliation script
- ✅ `stacks/core/docs/README.md` - GitOps documentation
- ✅ `stacks/core/docs/site/.gitignore` - Tracks all built files

### Deleted (Not GitOps)
- ❌ `setup_docs_stack.sh` - Replaced by gitops-sync.sh
- ❌ `SETUP_GUIDE.md` - Replaced by README.md

---

## Setup Instructions (10 minutes)

### Step 1: Create GitHub PAT

1. Go to: `https://github.com/settings/tokens`
2. Generate new token (classic)
3. Scopes: `repo` (full control of private repos)
4. Name: `living-docs-deploy`
5. Copy the token

### Step 2: Add GitHub Secret

1. Go to: `github.com/tmt-homelab/living-docs/settings/secrets/actions`
2. Add secret:
   - Name: `GH_PAT`
   - Value: [Your PAT from Step 1]
3. Add (if not exists):
   - Name: `CORVUS_API_KEY`
   - Value: [Your Corvus API token]

### Step 3: Deploy Stack to dockp04

```bash
# SSH to dockp04
ssh dockp04

# Create directory
sudo mkdir -p /mnt/docker/stacks/docs/site
sudo chown -R $USER:$USER /mnt/docker/stacks/docs

# Clone homelab-gitops and copy stack files
cd /mnt/docker/stacks/docs
git clone git@github.com:tmttodd/homelab-gitops.git temp-repo
cp temp-repo/stacks/core/docs/* .
rm -rf temp-repo

# Create initial placeholder
echo "Initializing..." > site/index.html

# Start container
docker compose up -d

# Verify
docker compose ps
curl http://127.0.0.1:8000/
```

### Step 4: (Optional) Set Up Auto-Sync

```bash
# Edit crontab
crontab -e

# Add this line (sync every 5 minutes)
*/5 * * * * /mnt/docker/stacks/docs/gitops-sync.sh >> /var/log/gitops-sync.log 2>&1
```

### Step 5: Test the Pipeline

1. Go to: `https://github.com/tmt-homelab/living-docs/actions`
2. Click "Sync and Deploy Documentation"
3. Click "Run workflow" → "Run workflow"
4. Watch it complete:
   - ✅ Checkout living-docs
   - ✅ Set up Python
   - ✅ Install dependencies
   - ✅ Run Corvus sync
   - ✅ Build MkDocs site
   - ✅ Checkout homelab-gitops
   - ✅ Deploy site to homelab-gitops
5. Wait 5 minutes (or run gitops-sync.sh manually)
6. Visit: `https://docs.themillertribe-int.org`

---

## How It Works

### Deployment Flow

1. **GitHub Actions runs** (scheduled, manual, or event-driven)
2. **Fetches Corvus data** → Generates markdown pages
3. **Builds MkDocs site** → Static HTML in `_site/`
4. **Checks out homelab-gitops** → Using GH_PAT
5. **Syncs site files** → `rsync _site/ stacks/core/docs/site/`
6. **Commits to homelab-gitops** → `git commit -m "deploy: update site"`
7. **Pushes to GitHub** → Triggers reconciliation on dockp04

### Reconciliation Flow

1. **cron runs** (every 5 min) or **manual trigger**
2. **git pull** → Updates homelab-gitops on dockp04
3. **rsync** → Copies new site files to `/mnt/docker/stacks/docs/site/`
4. **docker compose restart** → Reloads container
5. **health check** → Verifies site is accessible

---

## GitOps Benefits

✅ **Declarative**: docker-compose.yml defines desired state  
✅ **Versioned**: All changes in Git, full audit trail  
✅ **Rollback**: `git revert` + gitops-sync.sh  
✅ **No SSH**: No manual SSH keys or imperative scripts  
✅ **Secrets**: 1Password Connect for runtime secrets  
✅ **Reconciliation**: gitops-sync.sh ensures actual = desired  
✅ **Self-healing**: Cron automatically syncs drift  

---

## Troubleshooting

### Workflow fails at "Checkout homelab-gitops"
- **Cause**: Invalid GH_PAT or insufficient permissions
- **Fix**: Regenerate PAT with `repo` scope

### Site not updating on dockp04
- **Cause**: gitops-sync.sh not running or failing
- **Fix**: Run manually: `/mnt/docker/stacks/docs/gitops-sync.sh`

### Container not starting
- **Cause**: docker-compose.yml syntax error or port conflict
- **Fix**: `docker compose logs docs`

### Caddy returns 502
- **Cause**: Container not running or not healthy
- **Fix**: `docker compose ps` and `curl http://127.0.0.1:8000/`

---

## Next Steps

### Phase 3: nemoclaw Integration
- Create `scripts/nemoclaw_docs_sync.py`
- Add validation step to workflow
- Set up notifications/alerts

### Phase 4: Monitoring
- Add health checks to monitoring dashboard
- Configure alerts for failed deployments
- Track site uptime

---

## References

- **GitOps README**: `homelab-gitops/stacks/core/docs/README.md`
- **Project Context**: `living-docs/PROJECT_CONTEXT.md`
- **Workflow**: `living-docs/.github/workflows/sync-docs.yml`
- **Sync Script**: `homelab-gitops/stacks/core/docs/gitops-sync.sh`

---

*GitOps Pattern 2 Implementation Complete*  
*All state in Git • Declarative • Reconciled*
