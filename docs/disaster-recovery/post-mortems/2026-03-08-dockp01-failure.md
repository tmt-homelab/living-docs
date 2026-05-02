# Post-Mortem: dockp01 Storage Failure -- 2026-03-08

> **Severity**: P1 - Catastrophic
> **Status**: Resolved (fresh rebuild in progress)
> **Duration**: Ongoing recovery
> **Author**: Todd Miller

---

## Executive Summary

On 2026-03-08, the PERC H730P RAID controller on dockp01 failed and lost all VD (Virtual Drive) configuration. During the recovery attempt, Fast Initialization was performed which **wiped all ZFS labels** on the 8 SSDs, resulting in **complete data loss** on dockp01.

**Impact**:
- All Docker volumes lost (GitLab, OpenBao, PostgreSQL, Redis, etc.)
- All service configurations lost
- All container data lost
- **80+ services offline**

**Root Cause**: PERC H730P controller failure during hot-swap GPU installation, compounded by ZFS label destruction during recovery.

**Lesson Learned**: ZFS on hardware RAID requires off-controller backups. Relying on ZFS snapshots alone is insufficient when the RAID controller itself fails.

---

## Timeline

### 2026-03-08 00:00 - Initial Failure

**Event**: PERC H730P controller lost VD configuration during GPU installation hot-swap.

**Symptoms**:
- dockp01 became unreachable via SSH
- iDRAC showed controller in degraded state
- All 8 SSDs showed as "unconfigured good" in PERC BIOS

**Immediate Action**:
1. Powered down dockp01
2. Reseated PERC H730P controller
3. Powered on and entered PERC BIOS

### 2026-03-08 01:30 - First Recovery Attempt (Mistake #1)

**Decision**: Attempted to recover VD configuration from NVRAM backup.

**Result**: NVRAM backup was corrupted/outdated. VD could not be recovered.

**Action Taken**: Created new Virtual Drive with same configuration (8x SSD RAID 10).

**Critical Error**: Fast Initialization was enabled (default), which **wrote zeros to all disks**, destroying ZFS labels.

### 2026-03-08 03:00 - Realization

**Discovery**: ZFS pool `ai` and `docker` were completely gone.

**Verification**:
```bash
zpool list
# No pools found

zpool status
# No active pools
```

**Data Loss Confirmed**: All Docker volumes, GitLab repositories, OpenBao secrets, and service configs were lost.

### 2026-03-08 04:00 - Second GPU Installation

**Event**: RTX PRO 4500 Blackwell GPU installation required physical removal of NVMe drive.

**Complication**: PERC controller was reseated, triggering **another Fast Init** on the SSDs.

**Result**: Second destruction of any remaining ZFS metadata.

### 2026-03-08 06:00 - Decision Point

**Options Considered**:
1. Attempt ZFS recovery from disk (low probability of success)
2. Fresh rebuild from GitOps + secrets backup
3. Restore from TrueNAS backup (if available)

**Decision**: **Option 2 - Fresh rebuild**.

**Rationale**:
- ZFS labels were overwritten (unrecoverable)
- GitOps repo (`homelab-gitops`) was intact on Mac
- 1Password Connect backup existed for secrets
- GitHub backup existed for code/repos

---

## What Was Lost

### Docker Volumes (Complete Loss)

| Volume | Purpose | Recoverable? |
|--------|---------|--------------|
| gitlab_gitlab-data | GitLab repositories | No (redundant on GitHub) |
| openbao_vault | Secrets storage | No (restore from 1Password) |
| postgres_litellm | LiteLLM database | No (rebuild from scratch) |
| postgres_authentik | Authentik users | No (recreate users) |
| prefect_postgres | Prefect flows | No (redeploy flows) |
| All other volumes | Service data | No (redeploy from GitOps) |

### Configuration Files (Lost but Reconstructible)

- Docker Compose files (in GitOps repo)
- Caddyfile (in GitOps repo)
- Service configs (in GitOps repo)
- Ansible playbooks (in ansible/ repo)

### Irrecoverable Data

- GitLab CI/CD variables (must be re-entered)
- Authentik users and providers (must be recreated)
- Prefect flow runs and history (lost)
- LiteLLM API keys and teams (must be regenerated)
- Home Assistant entity states and history

---

## Recovery Strategy

### Phase 1: Infrastructure Restoration (Complete)

- [x] Reinstall Ubuntu 24.04.3 LTS on dockp01
- [x] Configure PERC H730P with 8x SSD RAID 10
- [x] Install Docker Engine + NVIDIA Container Toolkit
- [x] Configure ZFS pools (`ai` + `docker`)
- [x] Setup SSH keys and git credentials

### Phase 2: Secrets Recovery (In Progress)

- [ ] Deploy 1Password Connect on dockp01
- [x] Restore secrets from 1Password Connect (OpenBao no longer used)
- [ ] Regenerate all service API keys
- [ ] Reconfigure Authentik providers
- [ ] Restore GitLab CI/CD variables

### Phase 3: Service Redeployment (Pending)

- [ ] Deploy core stack (Caddy, Authentik, PostgreSQL, Redis)
- [ ] Deploy AI stack (vLLM, LiteLLM, Open WebUI, Milvus)
- [ ] Deploy automation stack (Prefect, Admin API)
- [ ] Deploy monitoring stack (Netdata, Uptime Kuma)
- [ ] Verify all services healthy

### Phase 4: Validation (Pending)

- [ ] Test all external URLs
- [ ] Verify SSO login
- [ ] Test AI model inference
- [ ] Verify DNS resolution
- [ ] Run full health check

---

## Root Cause Analysis

### Primary Cause: Hardware Failure

**PERC H730P Controller**: The RAID controller failed during a hot-swap GPU installation. This is unusual but not unprecedented for Dell PERC cards.

**Contributing Factor**: Hot-swap operation while system was powered on. Best practice is to power down before adding/removing PCIe devices.

### Secondary Cause: Recovery Procedure Error

**Fast Initialization**: When creating a new VD, Fast Init was enabled by default. This writes zeros to all disks, destroying any existing filesystem metadata (including ZFS labels).

**Lesson**: Always use **Full Initialization** when attempting recovery on disks that may contain data. Or better: **do not create a new VD until you've attempted data recovery**.

### Tertiary Cause: Backup Gap

**ZFS Snapshots Only**: The backup strategy relied on ZFS snapshots stored on the same host. When the RAID controller failed AND the disks were wiped, both the data AND the snapshots were lost.

**Missing**: Off-host or off-site backup of critical data.

---

## Corrective Actions

### Immediate (Completed)

1. **Switched to GitHub for Git hosting** — GitLab → GitHub migration
2. **Switched to 1Password Connect for secrets** — OpenBao → 1Password for M2M credentials
3. **Established off-host backups** — Critical repos now backed up to GitHub

### Short-Term (In Progress)

1. **Deploy 1Password Connect on all hosts** — Consistent secrets management
2. **Document recovery procedures** — This post-mortem + runbooks
3. **Create family emergency guide** — Non-technical recovery steps

### Long-Term (Planned)

1. **Implement true off-site backup** — Backblaze B2 or similar for critical data
2. **ZFS replication to dockp04** — Real-time replication to separate host
3. **Regular DR testing** — Quarterly recovery drills
4. **Hardware redundancy** — Spare PERC controller on hand

---

## What Went Well

1. **GitOps repo was safe** — `homelab-gitops` on GitHub allowed full reconstructability
2. **1Password Connect existed** — Secrets could be recovered from cloud
3. **Documentation was current** — CLAUDE.md and infra-docs had accurate host specs
4. **iDRAC access worked** — Out-of-band management allowed remote troubleshooting
5. **No physical damage** — Only controller failed, not the disks themselves

---

## What Went Poorly

1. **Hot-swap GPU installation** — Should have powered down first
2. **Fast Init during recovery** — Destroyed any chance of ZFS recovery
3. **No off-host ZFS snapshots** — All data on single host
4. **No DR runbook** — Had to figure out recovery steps during crisis
5. **No backup verification** — Didn't know backups were incomplete until failure

---

## Metrics

| Metric | Value |
|--------|-------|
| **Time to Detect** | < 5 minutes |
| **Time to Diagnose** | ~2 hours |
| **Time to Decision** | ~3 hours |
| **Time to Rebuild OS** | ~4 hours (estimated) |
| **Time to Full Recovery** | TBD (in progress) |
| **Data Lost** | 100% of dockp01 volumes |
| **Services Affected** | 80+ containers |
| **Users Affected** | Family + any external users |

---

## Lessons Learned

### Technical Lessons

1. **ZFS on hardware RAID is a double-ed sword** — ZFS provides data integrity, but RAID controller failure makes ZFS useless without backups.

2. **Hot-swap PCIe is risky** — Even "hot-swap capable" hardware should have power cycled before adding/removing cards.

3. **Fast Init is destructive** — Always verify you're not wiping data before initializing a VD.

4. **GitOps saves lives** — Having all compose files in Git allowed full reconstruction.

5. **Separation of concerns** — Secrets in 1Password (cloud) + compose files in GitHub + data on ZFS = better resilience.

### Operational Lessons

1. **Document before disaster** — This post-mortem is easier to write now than after the fact.

2. **Test your backups** — A backup you can't restore is not a backup.

3. **Have a DR runbook** — Step-by-step procedures reduce panic and errors.

4. **Family needs to know** — Non-technical family members need simple emergency procedures.

5. **Post-mortems are mandatory** — Every P1 incident gets documented, no exceptions.

---

## Action Items

| Item | Owner | Status | Due Date |
|------|-------|--------|----------|
| Complete dockp01 rebuild | Todd | In Progress | 2026-03-15 |
| Deploy 1Password Connect on all hosts | Todd | In Progress | 2026-03-12 |
| Write DR runbook (dockp01 rebuild) | Scribe | Pending | 2026-03-13 |
| Create family emergency guide | Herald | Pending | 2026-03-13 |
| Setup Backblaze B2 backup | Todd | Pending | 2026-03-20 |
| Configure ZFS replication to dockp04 | Architect | Pending | 2026-03-25 |
| Schedule quarterly DR drill | Planner | Pending | 2026-04-01 |
| Order spare PERC H730P controller | Todd | Pending | 2026-03-15 |

---

## References

- [dockp01 Rebuild Procedure](../recovery-procedures/dockp01-rebuild.md)
- [Physical Hosts Documentation](../../infrastructure/hosts.md)
- [Family Guide](../../getting-started/family-guide.md)
- [Emergency Contacts](../../getting-started/emergency-contacts.md)

---

*Post-mortem created: 2026-03-11*
*Last updated: 2026-03-11*
*Status: Active recovery in progress*
