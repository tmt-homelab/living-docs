# Operations Runbooks Overview

> **Purpose**: Standard operating procedures for routine tasks

## Available Runbooks

| Runbook | Purpose | Agent |
|---------|---------|-------|
| [Container Health](container-health.md) | Check container status, resources | Sentinel |
| [GPU OOM](gpu-oom.md) | Resolve GPU memory exhaustion | Responder |
| [Network Troubleshooting](network-troubleshooting.md) | Diagnose connectivity issues | Responder |
| [Secret Rotation](secret-rotation.md) | Rotate API keys and tokens | Changemaker |
| [Docker Host Restart](docker-host-restart.md) | Safe host reboot procedure | Responder |

## Runbook Format

Each runbook follows this structure:

```
# [Runbook Name]
> Purpose: [What this runbook covers]
> Severity: [P1/P2/P3/P4]
> Agent: [Responsible agent]

## Symptoms
[What triggers this runbook]

## Immediate Response
[First steps within 5 minutes]

## Investigation
[Diagnosis procedures]

## Remediation
[Fix steps]

## Prevention
[Long-term fixes]

## Escalation
[When to involve Todd]
```

## Creating New Runbooks

1. Copy template from existing runbook
2. Fill in purpose, symptoms, procedures
3. Add to this overview
4. Update mkdocs.yml navigation
