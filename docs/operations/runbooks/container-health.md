# Container Health Check Runbook

> **Purpose**: Daily/weekly container health verification
> **Frequency**: Daily (automated), Weekly (manual review)
> **Agent**: Sentinel

---

## Quick Health Check (2 minutes)

### All Hosts Status

```bash
# dockp01 (AI Compute)
ssh tmiller@192.168.20.15 "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}' | sort"

# dockp02 (AI Compute)
ssh tmiller@192.168.20.16 "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}' | sort"

# dockp04 (Infrastructure)
ssh tmiller@192.168.20.18 "sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Health}}' | sort"
```

### Expected Output

All containers should show:
- `Up X minutes/hours`
- `healthy` (if healthcheck defined)

**Red flags**:
- `Exited` or `Restarting`
- `unhealthy`
- `starting` for >5 minutes

---

## Detailed Health Check (10 minutes)

### Step 1: Check for Unhealthy Containers

```bash
# Find all unhealthy containers across hosts
for host in dockp01 dockp02 dockp04; do
  echo "=== $host ==="
  ssh tmiller@$host "sudo docker ps --filter health=unhealthy --format '{{.Names}}: {{.Status}}'"
  ssh tmiller@$host "sudo docker ps --filter status=restarting --format '{{.Names}}: {{.Status}}'"
done
```

### Step 2: Check Resource Usage

```bash
# Top 10 CPU consumers
ssh tmiller@192.168.20.15 "sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}' | sort -t'%' -k2 -rn | head -11"
ssh tmiller@192.168.20.16 "sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}' | sort -t'%' -k2 -rn | head -11"
ssh tmiller@192.168.20.18 "sudo docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}' | sort -t'%' -k2 -rn | head -11"

# Top 10 Memory consumers
ssh tmiller@192.168.20.15 "sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}' | sort -h -rn | head -11"
```

### Step 3: Check GPU State (dockp01/dockp02)

```bash
# dockp01 GPU status
ssh tmiller@192.168.20.15 "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader"

# dockp02 GPU status
ssh tmiller@192.168.20.16 "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader"
```

**Normal ranges**:
- GPU Utilization: 80-100% (active inference) or 0-10% (idle)
- VRAM Usage: 85-95% (optimal), >95% (risk), <50% (underutilized)
- Temperature: 60-75°C (normal), 75-80°C (warm), >80°C (hot)

### Step 4: Check Disk Space

```bash
# All hosts
for host in dockp01 dockp02 dockp04; do
  echo "=== $host ==="
  ssh tmiller@$host "df -h /mnt/docker /mnt/ai 2>/dev/null | grep -v Filesystem"
done
```

**Alert thresholds**:
- Warning: >70% used
- Critical: >85% used
- Emergency: >95% used

---

## Common Issues and Fixes

### Container Restarting Loop

**Symptoms**: Container status shows `Restarting` or frequent restarts

**Diagnosis**:
```bash
# Check logs
sudo docker logs <container> --tail 100

# Check health
sudo docker inspect <container> --format '{{.State.Health.Status}}'
```

**Fixes**:
1. **Single restart**: `sudo docker restart <container>`
2. **Check config**: Verify env vars, volumes, network
3. **Check resources**: `sudo docker stats <container>`
4. **If persistent**: Escalate to incident response

### Container Unhealthy

**Symptoms**: Health check failing

**Diagnosis**:
```bash
# Get health check output
sudo docker inspect <container> --format '{{json .State.Health.Log}}' | jq

# Check service endpoint
curl -v http://localhost:<port>/health
```

**Fixes**:
1. **Wait**: Some services take time to start (vLLM: 3-5 min)
2. **Restart**: `sudo docker restart <container>`
3. **Check dependencies**: Database, network, secrets
4. **Check logs**: Look for startup errors

### High Memory Usage

**Symptoms**: Container using >90% of memory limit

**Diagnosis**:
```bash
sudo docker stats <container> --no-stream
sudo docker inspect <container> --format '{{.HostConfig.Memory}}'
```

**Fixes**:
1. **Restart**: May clear memory leaks
2. **Increase limit**: Edit compose file, increase `memory`
3. **Investigate**: Check for memory leaks in app logs

### GPU OOM (Out of Memory)

**Symptoms**: vLLM containers crash with CUDA OOM errors

**Diagnosis**:
```bash
# Check GPU memory
nvidia-smi

# Check container logs
sudo docker logs vllm-primary --tail 50
```

**Fixes**:
1. **Restart container**: `sudo docker restart vllm-primary`
2. **Reduce batch size**: Edit compose env vars
3. **Check for zombie processes**: `ps aux | grep vllm`
4. **See GPU OOM runbook** for detailed procedure

---

## Critical Containers List

Restarting these requires **NOTIFY** (tell Todd):

- `caddy` - All external access
- `authentik-server` / `authentik-worker` - SSO authentication
- `postgres` (any stack) - Database services
- `litellm` - AI gateway
- `prefect-server` / `prefect-worker` - Workflow orchestration
- `homeassistant` - Smart home
- `milvus-standalone` - Vector database

All other containers: **AUTO** restart is safe.

---

## Automated Health Check

### Daily Sentinel Check

The `infra-sync-continuous` Prefect flow runs health checks every 15 minutes:

```bash
# Check last run
sudo docker exec prefect-worker prefect deployment run 'infra-sync-continuous/infra-sync-continuous'

# View results
sudo docker logs sentinel-health --tail 50
```

### Uptime Kuma Status

Visual status dashboard:
- Internal: `http://192.168.20.15:3001`
- External: `https://status.themillertribe-int.org`

---

## Reporting

### Daily Summary (Automated)

Herald sends daily briefing with:
- Container count by status
- Unhealthy containers list
- Resource usage peaks
- GPU utilization summary

### Weekly Review (Manual)

Every Monday:
1. Run full health check above
2. Review weekly incident reports
3. Update runbooks with new issues
4. Archive old incident reports (>90 days)

---

## Escalation Matrix

| Issue | First Action | If Not Fixed |
|-------|--------------|--------------|
| Single non-critical container | Restart (AUTO) | Wait 15 min, check logs |
| Single critical container | Restart + NOTIFY | Escalate after 2nd restart |
| Multiple containers | Check shared dependency | Escalate immediately |
| All containers down | Check host status | Escalate immediately |
| GPU OOM | Restart vLLM | Reduce batch size, add runbook |

---

## Related Runbooks

- [GPU OOM](gpu-oom.md) - GPU memory exhaustion
- [Network Troubleshooting](network-troubleshooting.md) - Connectivity issues
- [Secret Rotation](secret-rotation.md) - Credential updates
- [Disaster Recovery](../recovery-procedures/dockp01-rebuild.md) - Full host rebuild

---

*Last updated: 2026-03-12*
*Version: 1.0*
