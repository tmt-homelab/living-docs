# Network Troubleshooting Runbook

> **Purpose**: Diagnose and resolve network connectivity issues
> **Severity**: P2 - Service Degraded
> **Agent**: Responder

## Symptoms

- Container cannot reach other services
- External services unreachable from container
- Intermittent connection timeouts
- DNS resolution failures

## Immediate Response (5 minutes)

### Step 1: Verify Container Network

```bash
# Check container network membership
sudo docker inspect <container> --format '{{json .NetworkSettings.Networks}}' | jq '.'

# Expected: Container on correct network (infra-services, ai-services, media, etc.)
```

### Step 2: Test Basic Connectivity

```bash
# From Docker host
ping -c 3 192.168.20.15  # dockp01
ping -c 3 192.168.20.18  # dockp04

# From container
sudo docker exec <container> ping -c 3 <target_host>
```

### Step 3: Check DNS Resolution

```bash
# From container
sudo docker exec <container> nslookup <service_name>

# Expected: Resolves to correct IP
```

## Investigation

### Check Docker Network State

```bash
# List networks
sudo docker network ls

# Inspect specific network
sudo docker network inspect infra-services | jq '.[].Containers'
```

### Check for IP Conflicts

```bash
# ARP table
ip neigh show | grep -v FAILED

# Check for duplicate IPs
sudo docker network inspect infra-services --format '{{range .Containers}}{{.IPv4Address}}{{end}}' | sort | uniq -d
```

### Check Firewall Rules

```bash
# UniFi IPS status (SSH to gateway)
# Check for blocked connections in UniFi controller
```

### Check Caddy Reverse Proxy

```bash
# Verify upstream is reachable
curl -s http://localhost:80/health

# Check Caddy logs
sudo docker logs caddy --tail 50 | grep -i error
```

## Common Issues

### Container on Wrong Network

**Symptoms**: Cannot reach services on other networks

**Fix**:
```bash
# Disconnect from wrong network
sudo docker network disconnect vlan200 <container>

# Connect to correct network
sudo docker network connect infra-services <container>
```

### DNS Resolution Fails

**Symptoms**: `nslookup` times out or returns NXDOMAIN

**Fix**:
```bash
# Check PowerDNS
ssh tmiller@192.168.20.250 "sudo docker logs pdns-auth --tail 50"

# Check recursor
ssh tmiller@192.168.20.250 "sudo docker logs pdns-recursor --tail 50"

# Wipe negative cache
ssh tmiller@192.168.20.250 "rec_control wipe-cache <domain>"
```

### IPvlan Port Publishing Not Working

**Symptoms**: Port not accessible despite container running

**Root Cause**: IPvlan networks don't support port publishing

**Fix**: Move container to bridge network
```yaml
# Update docker-compose.yml
networks:
  - infra-services  # NOT vlan200
```

## Escalation

**Escalate to Todd if**:
- Network requires VLAN changes (UniFi configuration)
- Persistent IP conflicts across multiple hosts
- Caddy reverse proxy misconfiguration requires review
