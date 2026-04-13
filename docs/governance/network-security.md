# Network Security

> **Last Updated**: 2026-03-12

## Overview

Network security is enforced through VLAN segmentation, firewall rules, and container network isolation.

## Network Topology

| VLAN | CIDR | Purpose |
|------|------|---------|
| 20 | 192.168.20.0/24 | Server/Infrastructure |
| 400 | 192.168.40.0/24 | IoT devices |
| 200 | 192.168.200.0/24 | Docker ipvlan |
| 500 | 192.168.50.0/24 | DMZ (public-facing) |

## Segmentation

### VLAN 20 (Infrastructure)

**Allowed hosts**: Docker hosts, DNS servers, management workstations
**Services**: SSH (22), Docker API (2375), all internal service ports

### VLAN 400 (IoT)

**Allowed hosts**: Smart home devices, sensors
**Outbound only**: No inbound connections from IoT to infrastructure

### VLAN 200 (Docker)

**Allowed hosts**: Container traffic only
**Services**: Internal container communication

### VLAN 500 (DMZ)

**Allowed hosts**: Public-facing services
**Inbound**: Cloudflare tunnels only

## Firewall Rules

### UniFi Firewall

| Rule | Source | Destination | Port | Action |
|------|--------|-------------|------|--------|
| 100 | Any | VLAN 20 | 22 | Allow (management) |
| 200 | VLAN 500 | VLAN 20 | 443 | Allow (HTTPS) |
| 300 | VLAN 400 | VLAN 20 | Any | Deny (IoT isolation) |
| 999 | Any | Any | Any | Deny (default) |

### Docker Network Isolation

| Network | Isolation | Cross-Network Access |
|---------|-----------|---------------------|
| infra-services | Bridge | Controlled via Caddy |
| ai-services | Bridge | Internal only |
| media | Bridge | Internal only |
| vlan200 | ipvlan | Host routing only |

## Cloudflare Tunnel

### Configuration

- **Domain**: `*.themillertribe-int.org`
- **Tunnel**: `homelab-tunnel`
- **Authentication**: Cloudflare Access (OIDC via Authentik)

### Public Services

| Host | Internal Backend | Auth Required |
|------|------------------|---------------|
| docs.themillertribe-int.org | dockp04:8000 | No |
| ai.themillertribe-int.org | dockp01:4000 | Yes (SSO) |
| git.themillertribe-int.org | dockp04:8929 | Yes (SSO) |

### Access Policies

```
1. Cloudflare Access validates OIDC token from Authentik
2. If valid, route request to internal backend
3. If invalid, show authentication prompt
```

## Intrusion Prevention

### UniFi IPS

**Enabled**: Yes (all VLANs)

**Sensitive Rules**:
- SSH brute force detection
- Port scanning detection
- Known CVE exploitation attempts

### Exceptions

| Service | Reason | Action |
|---------|--------|--------|
| SSH (VLAN 20) | Admin access | Add to IPS exception list |
| Docker API | Internal communication | Whitelist source IPs |

## Monitoring

### Network Traffic Analysis

```bash
# Monitor inter-VLAN traffic
sudo tcpdump -i any -n host 192.168.40.0/24 and host 192.168.20.0/24
```

### Firewall Logs

```splunk
index=unifi (action=deny OR action=block) | timechart span=1h count by src_ip, dst_ip
```

### Anomaly Detection

| Metric | Threshold | Alert |
|--------|-----------|-------|
| Failed SSH attempts | >5 in 5 min | P2 |
| Cross-VLAN traffic | Sudden spike | P3 |
| Port scan detection | Any | P2 |

## Best Practices

### DO

- Keep VLANs segmented
- Use Cloudflare Access for public services
- Enable IPS on all VLANs
- Monitor firewall logs daily
- Rotate SSH keys quarterly

### DON'T

- Expose services directly (always use Cloudflare)
- Allow IoT devices to initiate connections to infrastructure
- Disable IPS without approval
- Share SSH credentials
- Use password authentication for SSH
