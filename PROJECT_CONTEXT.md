# Project Context: Living Docs Automated Pipeline

> **Last Updated**: 2026-04-13  
> **Status**: Phase 1 & 2 Complete (GitHub Actions + Dockp04 Stack), Phase 2 Setup Pending (Manual Steps)  
> **Owner**: Todd Miller

---

## Executive Summary

This project implements an automated documentation pipeline that:
1. Fetches operational data from Corvus (CMDB, incidents, changes)
2. Generates MkDocs documentation pages
3. Builds the static site
4. Deploys to dockp04 for serving via Caddy at `docs.themillertribe-int.org`

**Current State**: 
- GitHub Actions workflow updated to deploy to dockp04 via SSH
- Docker Compose stack created in homelab-gitops
- **Manual setup required on dockp04** (see Phase 2 Setup Guide)
- Workflow ready to test once SSH keys and secrets configured

---

## Architecture

### Target (GitOps Pattern 2: Git-to-Git)
```
┌─────────────────────────────────────────────────────────────┐
│  living-docs repo (github.com/tmt-homelab/living-docs)     │
│  - MkDocs source files                                       │
│  - GitHub Actions: Build → Push to homelab-gitops           │
└─────────────────────────────────────────────────────────────┘
                              ↓ (git push)
┌─────────────────────────────────────────────────────────────┐
│  homelab-gitops repo (github.com/tmttodd/homelab-gitops)   │
│  - stacks/core/docs/site/  ← Auto-committed built site      │
│  - stacks/core/docs/       ← Docker Compose config          │
└─────────────────────────────────────────────────────────────┘
                              ↓ (git pull + restart)
┌─────────────────────────────────────────────────────────────┐
│  dockp04                                                     │
│  - gitops-sync.sh (cron/watcher)                            │
│  - docker compose up -d                                     │
│  - Caddy proxy → docs.themillertribe-int.org                │
└─────────────────────────────────────────────────────────────┘
```

### GitOps Principles
- ✅ All state in Git (no manual SSH, no imperative deployment)
- ✅ Declarative configuration (docker-compose.yml)
- ✅ Secrets via 1Password Connect (not GitHub Secrets)
- ✅ Reconciliation via git pull + docker compose
- ✅ Audit trail in both repos
- ✅ Rollback via git revert

---

## Implementation Status

### ✅ Complete (Phase 1 & 2)

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Git repository | ✅ | `github.com/tmt-homelab/living-docs` | Pushed to main |
| MkDocs configuration | ✅ | `mkdocs.yml` | Material theme, navigation defined |
| Sync script | ✅ | `scripts/fetch_and_sync.py` | Fetches Corvus data |
| Documentation generator | ✅ | `scripts/sync_corvus.py` | Generates markdown pages |
| GitHub Actions workflow | ✅ | `.github/workflows/sync-docs.yml` | Builds MkDocs, **deploys to dockp04** |
| Dependencies | ✅ | `requirements.txt` | mkdocs-material, httpx |
| Documentation | ✅ | `README.md`, `DEPLOYMENT_SUMMARY.md`, `PROJECT_CONTEXT.md` | Project docs created |
| Docker Compose stack | ✅ | `homelab-gitops/stacks/core/docs/` | GitOps-managed |
| GitOps sync script | ✅ | `homelab-gitops/stacks/core/docs/gitops-sync.sh` | Reconciliation loop |
| GitOps README | ✅ | `homelab-gitops/stacks/core/docs/README.md` | Architecture docs |

### ⏳ Pending (Manual Setup)

| Component | Status | Priority | Notes |
|-----------|--------|----------|-------|
| Stack deployment | ❌ Not run | High | Copy files to /mnt/docker/stacks/docs on dockp04 |
| GH_PAT secret | ❌ Not configured | High | Create PAT with repo scope |
| Container start | ❌ Not started | High | docker compose up -d |
| Pipeline test | ❌ Not tested | High | Trigger workflow manually |
| Cron sync | ⏳ Optional | Low | Set up gitops-sync.sh cron job |

---

## Configuration Requirements

### GitHub Secrets (Required for Deployment)

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `CORVUS_API_KEY` | [Corvus API token] | Authenticate to Corvus API (runtime) |
| `GH_PAT` | [Personal Access Token] | Cross-repo deployment (living-docs → homelab-gitops) |

**Note**: Runtime secrets (CORVUS_API_KEY) are injected via **1Password Connect** on dockp04, not GitHub Secrets. GitHub Secrets are only used for deployment authentication.

### dockp04 Setup (One-Time)

```bash
# Create stack directory
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

# Optional: Set up cron for auto-sync
crontab -e
# Add: */5 * * * * /mnt/docker/stacks/docs/gitops-sync.sh >> /var/log/gitops-sync.log 2>&1
```

### Caddy Configuration (No Changes Needed)

Current config already proxies correctly:
```caddyfile
docs.themillertribe-int.org {
    import internal_tls
    reverse_proxy {
        dynamic a 192.168.20.18 8000 {
            refresh 30s
            versions ipv4
        }
        import resilient_proxy
    }
}
```

---

## Key Files

| File | Purpose | Last Modified |
|------|---------|---------------|
| `.github/workflows/sync-docs.yml` | CI/CD pipeline definition | 2026-04-13 |
| `scripts/fetch_and_sync.py` | Corvus data fetcher | 2026-04-12 |
| `scripts/sync_corvus.py` | Documentation generator | 2026-04-12 |
| `mkdocs.yml` | MkDocs configuration | 2026-04-12 |
| `requirements.txt` | Python dependencies | 2026-04-13 |
| `README.md` | Project documentation | 2026-04-13 |
| `DEPLOYMENT_SUMMARY.md` | Implementation history | 2026-04-13 |
| `PROJECT_CONTEXT.md` | This file - project memory | 2026-04-13 |

---

## Pending Decisions

### 1. Docker Stack Location
**Question**: Should the docs stack live in `homelab-gitops/stacks/core/docs/` or `homelab-ai/stacks/docs/`?

**Recommendation**: `homelab-gitops/stacks/core/docs/` - It's a core service, not AI-specific.

### 2. nemoclaw Flow Design
**Question**: Should nemoclaw:
- A) Just validate the built site (link checking, navigation)?
- B) Also update Corvus with documentation metadata?
- C) Both?

**Recommendation**: Start with A, evolve to C.

### 3. SSH Key Management
**Question**: Should the deploy key be:
- A) Dedicated key for this purpose (recommended)?
- B) Reuse existing SSH key?
- C) Use GitHub Actions OIDC + SSH?

**Recommendation**: A - Dedicated key with restricted permissions.

---

## Implementation Roadmap

### Week 1: Foundation (Current Sprint) - **IN PROGRESS**

- [x] Create Docker Compose stack on dockp04
- [x] Generate SSH deploy key (pending manual execution)
- [x] Add GitHub secrets (pending manual configuration)
- [x] Modify workflow to deploy to dockp04
- [ ] Test end-to-end pipeline (run setup_docs_stack.sh first)

### Week 2: nemoclaw Integration

- [ ] Design nemoclaw flow for docs validation
- [ ] Implement `nemoclaw_docs_sync.py`
- [ ] Add validation step to workflow
- [ ] Set up notifications/alerts

### Week 3: Polish & Documentation

- [ ] Write operational runbooks
- [ ] Document troubleshooting procedures
- [ ] Create monitoring dashboard (optional)
- [ ] Final review and handoff

---

## Troubleshooting Reference

### Common Issues

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Workflow fails at "Deploy to dockp04" | SSH key not configured | Verify `DOCKP04_SSH_KEY` secret and authorized_keys |
| Site not updating after deploy | Container not restarted | Add `docker compose restart` to deploy script |
| MkDocs build fails | Navigation path broken | Run `mkdocs build --strict` locally first |
| Corvus sync returns empty | API key invalid | Check `CORVUS_API_KEY` and network connectivity |
| Caddy returns 502 | Container not running | `docker compose ps` on dockp04 |

### Debug Commands

```bash
# On dockp04 - Check container status
cd /mnt/docker/stacks/docs
docker compose ps
docker compose logs -f

# Check site contents
ls -la /mnt/docker/stacks/docs/site/

# Manual rebuild
cd /mnt/docker/stacks/docs/source
mkdocs build --strict --site-dir ../site

# Test Caddy proxy
curl -v https://docs.themillertribe-int.org

# Check GitHub Actions logs
# https://github.com/tmt-homelab/living-docs/actions
```

---

## Related Systems

| System | URL | Purpose |
|--------|-----|---------|
| Corvus | `http://localhost:9420` | Operational data source |
| nemoclaw | `http://localhost:8100` | Automation/orchestration |
| Caddy | dockp04:443 | Reverse proxy |
| GitHub | `github.com/tmt-homelab/living-docs` | Source control + CI/CD |
| Authentik | `auth.themillertribe-int.org` | SSO (deprecated, not used for docs) |

---

## Notes for Future Sessions

### Starting a New Session

1. **Read this file first** - It contains the current state and pending work
2. **Check git history** - `git log --oneline` shows recent changes
3. **Review workflow** - `.github/workflows/sync-docs.yml` is the main automation
4. **Test locally** - `mkdocs serve` to preview changes

### Key Design Principles

- **Single source of truth**: Corvus → docs → published site
- **Automated everything**: No manual steps after initial setup
- **GitOps**: All changes via PRs, all deployments via CI/CD
- **Zero downtime**: Rolling updates, atomic deployments
- **Self-hosted**: Leverages existing dockp04 infrastructure

### What NOT to Do

- ❌ Don't edit docs in the `/site/` directory (it's auto-generated)
- ❌ Don't manually run `mkdocs serve` on dockp04 (use container)
- ❌ Don't hardcode secrets (use GitHub Secrets or 1Password)
- ❌ Don't push to main directly (use PRs)

---

## Contact & Escalation

- **Owner**: Todd Miller
- **Primary Contact**: [Internal Slack/Teams]
- **Escalation**: Check Corvus incidents for ongoing issues

---

*This document is maintained as part of the living documentation pipeline. Updates are automated via the sync workflow.*
