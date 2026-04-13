# Overview

Welcome to the TMT Homelab documentation. This page provides a high-level introduction to what this infrastructure is and how to navigate these docs.

---

## What Is This Homelab?

The Miller Tribe homelab is a **production-grade private cloud** running at home. It hosts:

- **AI/ML Services**: Large language models, embeddings, reranking, chat interfaces
- **Media Services**: Streaming, TV/movie acquisition, family media library
- **Smart Home**: Home Assistant, Zigbee automation, security cameras
- **Development**: Git hosting, CI/CD, automation pipelines
- **Core Infrastructure**: DNS, authentication, monitoring, secrets management

### Scale

| Resource | Count |
|----------|-------|
| Physical Servers | 4 (Dell PowerEdge + Jetson) |
| GPUs | 9 (RTX PRO 6000, 5000, A5000) |
| Total VRAM | ~684 GB |
| Storage | 523 TB (ZFS media pool) + 7 TB (SSD) |
| Docker Containers | 80+ |
| Domains | 2 (themillertribe.org, themillertribe-int.org) |

---

## Who Should Use This Documentation?

### Family Members
If you're a family member and something isn't working:
1. Go to [Family Guide](family-guide.md)
2. Check [Emergency Contacts](emergency-contacts.md)
3. Don't worry about the technical details — just follow the simple steps

### Operators (Todd + Designees)
If you're responsible for keeping things running:
1. Start with [Operations Runbooks](../operations/runbooks/overview.md)
2. Bookmark [Monitoring Dashboard](../services/monitoring/overview.md)
3. Know where the [Disaster Recovery Procedures](../disaster-recovery/recovery-procedures/overview.md) are

### Future Administrators
If you're taking over this infrastructure:
1. Read [Physical Hosts](../infrastructure/hosts.md) to understand the hardware
2. Study [Network Topology](../infrastructure/networking.md)
3. Review [Post-Mortems](../disaster-recovery/post-mortems/) to learn from past failures

---

## Documentation Philosophy

### Machine-Readable + Human-Readable
- **Machine**: `infra-docs/data/*.yaml` — Auto-synced from running infrastructure
- **Human**: This wiki — Curated guides, procedures, explanations

### Single Source of Truth
Every concept has exactly one canonical location. If you find duplicates, report them.

### Live Documentation
- Infrastructure data syncs automatically every 15 minutes
- Reports sync every 6 hours
- Manual updates reviewed quarterly

---

## How Documentation Is Organized

```
homelab-docs/
├── getting-started/     # First-time user guides
├── infrastructure/      # Hardware, network, storage
├── services/           # Service-specific docs
├── disaster-recovery/  # Recovery procedures, post-mortems
├── operations/         # Runbooks, monitoring, common tasks
├── security/           # Secrets, access control
├── reports/            # Operational reports
└── glossary.md         # Terms and acronyms
```

---

## Quick Start by Role

### I'm a Family Member
→ [Go to Family Guide](family-guide.md)

### I Need to Fix Something Right Now
→ [Go to Operations Runbooks](../operations/runbooks/overview.md)

### I'm Setting Up a New Service
→ [Go to Service Deployment](../operations/common-tasks.md)

### I'm Recovering from a Failure
→ [Go to Disaster Recovery](../disaster-recovery/recovery-procedures/overview.md)

---

## Contributing to Documentation

### Automatic Updates
- Infrastructure YAML files: Updated by `infra-sync` Prefect flow
- Reports: Synced by `report-sync` Prefect flow

### Manual Updates
When you make a change to infrastructure, update the relevant docs:
1. Edit the appropriate `.md` file
2. Commit with descriptive message
3. Create MR for review (if applicable)
4. Merge triggers auto-deploy

### Reporting Issues
Found outdated or incorrect information?
1. Create GitHub issue in `homelab-docs` repo
2. Tag with `documentation` label
3. Assign to appropriate workspace

---

## Support Channels

| Channel | Purpose |
|---------|---------|
| Slack #homelab | General discussion, non-critical alerts |
| Slack #homelab-alerts | Critical service alerts (automated) |
| Phone | P1 incidents (service completely down) |
| GitHub Issues | Feature requests, documentation updates |

---

## Related Documentation

- [Infrastructure GitOps Repo](https://github.com/tmttodd/homelab-gitops) — Docker Compose configs
- [Claude Workspaces](../../CLAUDE.md) — AI agent governance and workflows
- [Task Library](../../task-library/) — Standard operating procedures

---

*Last updated: 2026-03-11*
