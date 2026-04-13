# Project Context: Living Docs Automated Pipeline

> **Last Updated**: 2026-04-13  
> **Status**: Phase 1 Complete (GitHub Actions + Build), Phase 2 Pending (Dockp04 Deployment)  
> **Owner**: Todd Miller

---

## Executive Summary

This project implements an automated documentation pipeline that:
1. Fetches operational data from Corvus (CMDB, incidents, changes)
2. Generates MkDocs documentation pages
3. Builds the static site
4. Deploys to dockp04 for serving via Caddy at `docs.themillertribe-int.org`

**Current State**: GitHub Actions workflow is built but deploying to GitHub Pages. Needs modification to deploy to dockp04 instead.

---

## Architecture

### Current (As-Is)
```
┌─────────────────────────────────────────────────────────────┐
│  dockp04                                                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  MkDocs (dev mode) - python -m mkdocs serve :8000   │    │
│  └─────────────────────────────────────────────────────┘    │
│         ↑                                                    │
│         │ Manual updates (git pull, manual rebuild)          │
│  ┌──────┴──────────────────────────────────────────────┐    │
│  │  Git repo: ~/Documents/Claude/repos/homelab-docs/   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ Caddy proxy (from homelab-gitops Caddyfile)
         │
docs.themillertribe-int.org
```

### Target (To-Be)
```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions (self-hosted runner on dockp04)             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  1. Fetch Corvus data                               │    │
│  │  2. Generate docs via sync_corvus.py                │    │
│  │  3. Build MkDocs (mkdocs build)                     │    │
│  │  4. Deploy via SSH/rsync to dockp04                 │    │
│  │  5. Trigger nemoclaw validation                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  dockp04 (/mnt/docker/stacks/docs)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  docker-compose.yml                                 │    │
│  │  /site/  ← auto-updated built site                  │    │
│  │  /source/  ← git repo (read-only)                   │    │
│  │  mkdocs-material container (prod mode)              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ Caddy proxy (no changes needed)
         │
docs.themillertribe-int.org
```

---

## Implementation Status

### ✅ Complete (Phase 1)

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Git repository | ✅ | `github.com/tmt-homelab/living-docs` | Pushed to main |
| MkDocs configuration | ✅ | `mkdocs.yml` | Material theme, navigation defined |
| Sync script | ✅ | `scripts/fetch_and_sync.py` | Fetches Corvus data |
| Documentation generator | ✅ | `scripts/sync_corvus.py` | Generates markdown pages |
| GitHub Actions workflow | ✅ | `.github/workflows/sync-docs.yml` | Builds MkDocs, deploys to GitHub Pages |
| Dependencies | ✅ | `requirements.txt` | mkdocs-material, httpx |
| Documentation | ✅ | `README.md`, `DEPLOYMENT_SUMMARY.md` | Project docs created |

### ⏳ Pending (Phase 2)

| Component | Status | Priority | Notes |
|-----------|--------|----------|-------|
| Docker stack for docs | ❌ Not created | High | `homelab-gitops/stacks/core/docs/docker-compose.yml` |
| Workflow modification | ❌ Not updated | High | Replace GitHub Pages with SSH deploy to dockp04 |
| SSH deploy key | ❌ Not generated | High | GitHub → dockp04 SSH access |
| nemoclaw integration | ❌ Not created | Medium | `scripts/nemoclaw_docs_sync.py` |
| Initial dockp04 setup | ❌ Not done | High | Create directories, deploy compose file |
| Testing | ❌ Not done | High | End-to-end pipeline test |

---

## Configuration Requirements

### GitHub Secrets (Required)

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `CORVUS_API_KEY` | [Corvus API token] | Authenticate to Corvus API |
| `DOCKP04_USER` | `tmiller` (or similar) | SSH username for dockp04 |
| `DOCKP04_SSH_KEY` | [Private SSH key] | SSH authentication to dockp04 |
| `NEMOCLOW_URL` | `http://localhost:8100` (or internal URL) | nemoclaw endpoint |
| `NEMOCLOW_API_KEY` | [nemoclaw API token] | Authenticate to nemoclaw |

### dockp04 Setup (Required)

```bash
# Create directory structure
sudo mkdir -p /mnt/docker/stacks/docs/{source,site}
sudo chown -R $USER:$USER /mnt/docker/stacks/docs

# Generate SSH deploy key (if not existing)
ssh-keygen -t ed25519 -C "github-actions@living-docs" -f ~/.ssh/github-actions-deploy

# Add public key to dockp04 authorized_keys
cat ~/.ssh/github-actions-deploy.pub | sudo tee -a /home/tmiller/.ssh/authorized_keys

# Restrict key permissions
sudo chmod 600 /home/tmiller/.ssh/authorized_keys
```

### Caddy Configuration (No Changes Needed)

Current config already proxies correctly:
```caddyfile
docs.themillertribe-int.org {
    import internal_tls
    reverse_proxy {
        dynamic a 192.168.20.14 8000 {
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

### Week 1: Foundation (Current Sprint)

- [ ] Create Docker Compose stack on dockp04
- [ ] Generate SSH deploy key
- [ ] Add GitHub secrets
- [ ] Modify workflow to deploy to dockp04
- [ ] Test end-to-end pipeline

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
