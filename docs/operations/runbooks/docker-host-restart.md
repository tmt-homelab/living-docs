# Docker Host Restart Runbook

> **Purpose**: Safely restart a Docker host (planned maintenance)
> **Severity**: P2 - Service Degraded
> **Agent**: Responder

## Prerequisites

- Notify affected users (Herald sends notification)
- Verify backup status (no critical writes during reboot)
- Have physical/iDRAC access ready (in case network fails)

## Pre-Restart Checklist

### Step 1: Check Container Health

```bash
ssh tmiller@<host> "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | sort"
```

**Expected**: All critical containers healthy

### Step 2: Check Dependent Services

```bash
# Verify other hosts are stable
ssh tmiller@192.168.20.15 "sudo docker ps --filter health=unhealthy"
ssh tmiller@192.168.20.16 "sudo docker ps --filter health=unhealthy"
ssh tmiller@192.168.20.17 "sudo docker ps --filter health=unhealthy"
ssh tmiller@192.168.20.18 "sudo docker ps --filter health=unhealthy"
```

**Expected**: No unhealthy containers

### Step 3: Notify Users

```bash
# Herald sends Slack notification
# P2 Warning → #homelab-alerts
```

## Restart Procedure

### Step 4: Graceful Container Shutdown

```bash
# Stop non-critical containers first
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/media/docker-compose.yml down"
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/ai/docker-compose.yml down"

# Stop critical containers (in order)
ssh tmiller@<host> "sudo docker stop prefect-worker"
ssh tmiller@<host> "sudo docker stop authentik-worker"
ssh tmiller@<host> "sudo docker stop authentik-server"
ssh tmiller@<host> "sudo docker stop postgresql"
```

### Step 5: Restart Host

```bash
# SSH session will disconnect
ssh tmiller@<host> "sudo reboot"
```

### Step 6: Wait for Host to Come Online

```bash
# Wait 3-5 minutes
watch -n 5 'ssh tmiller@<host> "uptime"'  # From another terminal
```

### Step 7: Verify Host Health

```bash
# Check system state
ssh tmiller@<host> "uptime; free -h; df -h"

# Check Docker daemon
ssh tmiller@<host> "sudo systemctl status docker --no-pager"
```

### Step 8: Restart Containers

```bash
# Critical services first
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/core/docker-compose.yml up -d"

# Wait for dependencies
sleep 30

# AI services
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/ai/docker-compose.yml up -d"

# Media services
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/media/docker-compose.yml up -d"

# Other services
ssh tmiller@<host> "sudo docker compose -f /mnt/docker/stacks/monitoring/docker-compose.yml up -d"
```

### Step 9: Verify All Containers Healthy

```bash
ssh tmiller@<host> "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | sort"
```

**Expected**: All containers `Up (healthy)` or `Up`

### Step 10: Verify Services Accessible

```bash
# Test reverse proxy
curl -s https://docs.themillertribe-int.org/

# Test critical services
curl -s https://auth.themillertribe-int.org/-/health/live/
curl -s http://litellm:4000/health
```

## Post-Restart Monitoring

### Step 11: Monitor for 30 Minutes

```bash
# Watch container logs for errors
ssh tmiller@<host> "sudo docker logs --tail 50 --follow $(sudo docker ps --format '{{.Names}}')"
```

**Expected**: No repeated errors, containers stable

### Step 12: Notify Resolution

```bash
# Herald sends recovery notification
# #homelab-alerts: "All services restored on <host>"
```

## Emergency Recovery

### If Host Doesn't Come Online

1. **Check iDRAC**: `https://192.168.30.<host-number>/`
2. **Power cycle via iDRAC**
3. **Check physical console** (if remote fails)

### If Containers Won't Start

```bash
# Check logs
ssh tmiller@<host> "sudo docker logs <container> --tail 100"

# Check volumes
ssh tmiller@<host> "sudo docker volume ls"

# Check network
ssh tmiller@<host> "sudo docker network ls"

# Escalate to Todd if persistent
```

## Rollback

**If issues persist after 30 minutes**:

1. Stop all containers
2. Revert any config changes made before restart
3. Restart host again (clean slate)
4. Escalate to Todd if still failing
