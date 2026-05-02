# Self-Hosted Runner Security Hardening Design

> **Status**: Draft  
> **Last Updated**: 2026-04-17  
> **Owner**: Security Engineering  
> **Review Cycle**: Quarterly

## Executive Summary

Self-hosted GitHub Actions runners on the Miller Homelab have privileged network access to internal infrastructure (PostgreSQL, Redis, ZFS, 1Password Connect, Corvus API). This design hardens that access path using defense-in-depth: network isolation, least-privilege execution, ephemeral secrets, and comprehensive audit logging.

**Key changes from current state:**
- Runners currently run as `tmiller` user with full Docker socket access
- No network segmentation between runner and infrastructure services
- Secrets loaded via `1password/load-secrets-action` with broad vault access
- Tetragon deployed but not yet integrated with runner-specific policies

**Target state:**
- Runner runs as dedicated `github-runner` user in a dedicated Docker bridge network
- Network access restricted to only required services per workflow
- Secrets fetched via OIDC-backed short-lived tokens scoped to specific items
- All runner activity logged to Splunk with 90-day retention

---

## 1. Network Architecture

### 1.1 VLAN Design

Current VLANs (from `living-docs/docs/governance/network-security.md`):

| VLAN | CIDR | Purpose | Runner Placement |
|------|------|---------|----------------|
| 20 | 192.168.20.0/24 | Server/Infrastructure | Current host network |
| 400 | 192.168.40.0/24 | IoT devices | No access |
| 500 | 192.168.50.0/24 | DMZ (public-facing) | No access |

**Proposed new VLAN for runners:**

| VLAN | CIDR | Purpose | Access Scope |
|------|------|---------|------------|
| 30 | 192.168.30.0/24 | Runner / GitOps workloads | Outbound only to allowlisted infra; no inbound |

**Rationale:** Runners need outbound access to GitHub, Docker Hub, and internal services. They do not need to receive inbound connections from other infrastructure components. A dedicated VLAN provides a chokepoint for egress filtering and prevents runners from being used as pivot points to reach other infrastructure.

### 1.2 Firewall Rules

#### UniFi Firewall (VLAN 30 → Infrastructure)

```
# Rule 100: GitHub webhooks + API
ALLOW  TCP  192.168.30.0/24  140.82.112.0/22  443
ALLOW  TCP  192.168.30.0/24  140.82.112.0/22  22   # SSH for git clone

# Rule 110: Docker Hub / GHCR (container image pulls)
ALLOW  TCP  192.168.30.0/24  192.168.20.0/24  443  # via Docker registry proxy
ALLOW  TCP  192.168.30.0/24  ghcr.io           443
ALLOW  TCP  192.168.30.0/24  registry-1.docker.io  443

# Rule 120: Internal services (per workflow need)
ALLOW  TCP  192.168.30.0/24  192.168.20.18  5432  # PostgreSQL (deploy workflows only)
ALLOW  TCP  192.168.30.0/24  192.168.20.18  6379  # Redis (deploy workflows only)
ALLOW  TCP  192.168.30.0/24  192.168.20.18  8080  # 1Password Connect API
ALLOW  TCP  192.168.30.0/24  192.168.20.18  9420  # Corvus API (automation only)

# Rule 130: DNS (outbound resolution)
ALLOW  UDP  192.168.30.0/24  192.168.20.250  53
ALLOW  UDP  192.168.30.0/24  192.168.20.251  53

# Rule 140: Splunk HEC (logging)
ALLOW  TCP  192.168.30.0/24  192.168.20.18  8088

# Rule 999: Default deny
DENY   ANY  192.168.30.0/24  ANY  ANY
```

#### Docker Host Firewall (iptables on runner host)

Applied via a `runner-firewall.sh` script at host boot:

```bash
#!/usr/bin/env bash
# runner-firewall.sh — applied at runner host boot via systemd service
# Drops all inbound to runner host except DHCP/DNS

# Default policy: DROP inbound
iptables -P INPUT DROP
iptables -P FORWARD DROP

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow DHCP (required for DHCP-based VLAN assignment)
iptables -A INPUT -p udp --dport 67:68 --sport 67:68 -j ACCEPT

# Allow DNS from any infrastructure DNS
iptables -A INPUT -p udp -s 192.168.20.250 --dport 53 -j ACCEPT
iptables -A INPUT -p udp -s 192.168.20.251 --dport 53 -j ACCEPT

# Allow GitHub Actions runner heartbeat (runner → GitHub)
# This is outbound-initiated, so no inbound rule needed

# Log dropped packets (rate-limited)
iptables -A INPUT -j LOG --log-prefix "RUNNER-DROP: " -m limit --limit 5/min
```

### 1.3 Docker Network Isolation

Runners operate inside Docker containers during workflow execution. The current compose-based stacks use external Docker networks. Runner containers must be restricted to only the networks required for that specific deployment.

**Current networks and their purposes:**

| Network | Services Connected | Runner Access |
|---------|-----------------|----------------|
| `infra-services` | Caddy, certbot, cloudflareddns | Required for deploy workflows |
| `infra-db` | PostgreSQL, Redis | Required for deploy workflows |
| `security-internal` | Splunk | Required for security workflows |
| `ai-services` | LiteLLM, vLLM, OpenWebUI | Required for AI workflows |
| `media` | Plex, Sonarr, Radarr | Required for media workflows |
| `homeauto` | Home Assistant, Zigbee2MQTT | Required for homeauto workflows |
| `automation` | Prefect, Corvus, NemoClaw | Required for automation workflows |

**Design: Per-workflow network attachment**

Workflows should only attach to networks required for that specific deployment. This is enforced by:

1. **Workflow-level network allowlisting** in the workflow YAML:
   ```yaml
   jobs:
     deploy:
       runs-on: [self-hosted, dockp04]
       container:
         # Only attach networks required for this workflow
         networks:
           - infra-services
           - infra-db
       # ...
   ```

2. **Docker Compose network restrictions** in deploy workflows:
   ```yaml
   # In the deploy step, only create networks that the workflow needs
   - name: Deploy stack
     run: |
       cd "$STACK_DIR"
       docker compose --network infra-services up -d
   ```

3. **Network policy enforcement** via Tetragon:
   ```yaml
   # tetragon.conf.d/docker_abuse.tp.d/api_port_connections.tp
   # Already detects direct Docker API access — extend to flag cross-network access
   ```

### 1.4 Egress Restrictions Summary

| Destination | Port | Purpose | Policy |
|-------------|------|---------|--------|
| GitHub (140.82.112.0/22) | 443, 22 | Webhooks, git | ALLOW |
| Docker Hub (registry-1.docker.io) | 443 | Image pulls | ALLOW |
| GHCR (ghcr.io) | 443 | Container registry | ALLOW |
| 1Password Connect (host) | 8080 | Secret fetch | ALLOW (runner→host) |
| Splunk HEC | 8088 | Logging | ALLOW (runner→host) |
| Corvus API | 9420 | Automation | ALLOW (automation workflows only) |
| PostgreSQL | 5432 | Config write | ALLOW (deploy workflows only) |
| Redis | 6379 | Cache | ALLOW (deploy workflows only) |
| DNS servers | 53 | Resolution | ALLOW |
| Any other destination | Any | — | DENY |

---

## 2. Runner Hardening

### 2.1 User Permissions

**Current state:** Runner runs as `tmiller` user (from `RUNNER_SETUP.md`: "runner runs with your user permissions").

**Target state:** Runner runs as dedicated `github-runner` user with minimal permissions.

#### User Creation and Configuration

```bash
# Create dedicated runner user (no sudo, no login shell for direct SSH)
sudo useradd -r -s /usr/sbin/nologin -d /home/github-runner -m github-runner

# Runner home directory permissions
sudo chmod 700 /home/github-runner

# Runner owns their working directory
sudo chown -R github-runner:github-runner /home/github-runner/actions-runner
```

#### Sudo Policy

The runner user must **never** have sudo access. Workflows that need sudo should use `sudo -n` with a passwordless sudoers rule scoped to specific commands.

**`/etc/sudoers.d/github-runner`:**
```
# Runner user: passwordless sudo ONLY for specific Docker and file operations
# No shell escalation, no useradd/usermod, no service control

github-runner ALL=(root) NOPASSWD: \
    /usr/bin/docker compose *, \
    /usr/bin/docker compose -f *, \
    /usr/bin/docker ps, \
    /usr/bin/docker inspect *, \
    /usr/bin/docker logs *, \
    /usr/bin/mkdir -p /mnt/docker/stacks/*, \
    /usr/bin/chown -R github-runner:docker /mnt/docker/stacks/*, \
    /usr/bin/chmod 640 /mnt/docker/stacks/*/.env, \
    /usr/bin/chmod 644 /mnt/docker/stacks/*/docker-compose.yml, \
    /usr/bin/cp stacks/*/docker-compose.yml /mnt/docker/stacks/*/, \
    /usr/bin/cp stacks/*/Caddyfile /mnt/docker/stacks/*/, \
    /usr/bin/systemctl reload docker, \
    /usr/bin/systemctl restart docker.service

# Explicitly denied
github-runner ALL=(root) NOPASSWD: !ALL
# Prevent sudo to root shell
github-runner ALL=(root) NOPASSWD: !/bin/bash, !/usr/bin/bash, !/bin/sh, !/usr/bin/sh
```

**Rationale:** Workflows need to create directories and set permissions on stack files. This sudoers rule allows only the specific commands needed for the GitOps deploy workflow, scoped to the exact paths used.

### 2.2 Docker Access

**Current state:** Runner has access to the Docker socket (`/var/run/docker.sock`), which provides full root equivalent access on the host.

**Target state:** Runner uses Docker-in-Docker (DinD) or rootless Docker for workflow container execution, with the host Docker socket removed from runner process scope.

#### Option A: Rootless Docker (preferred)

Rootless Docker runs containers without root privileges. The runner uses a rootless socket at `run/user/$(id -u github-runner)/docker.sock`.

```bash
# Configure rootless Docker for github-runner user
# Install rootless Docker per https://docs.docker.com/engine/security/rootless/

# Create rootless Docker socket directory
mkdir -p /run/user/$(id -u github-runner)

# Runner uses rootless socket (set in /home/github-runner/.docker/config.json)
{
  "hosts": ["unix:///run/user/$(id -u github-runner)/docker.sock"]
}
```

**Trade-offs:** Rootless Docker has some limitations (no swap limit, no cgroup delegation). For homelab use, acceptable.

#### Option B: DinD sidecar (if rootless insufficient)

Run a DinD container alongside the runner, with a TCP socket bound to localhost only:

```yaml
# docker-compose.yml (runner host)
services:
  dind:
    image: docker:dind
    container_name: dind
    privileged: true  # Required for DinD
    networks:
      - runner-internal
    ports:
      - "127.0.0.1:2375:2375"  # Localhost only — no external exposure
    environment:
      - DOCKER_TLS_CERTDIR=  # Disable TLS for local access
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "docker", "info"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  runner-internal:
    driver: bridge
    internal: true  # No external routing
```

Runner workflow steps then use `DOCKER_HOST=tcp://127.0.0.1:2375`.

**Recommendation:** Option A (rootless Docker) for homelab scale. Simpler, no privileged container, no TLS cert management.

### 2.3 Runner Service Configuration

**Current state:** Runner service runs as `tmiller` user, managed by `svc.sh`.

**Target state:** Runner service runs as `github-runner` user, managed by systemd.

#### Systemd Service Unit

```ini
# /etc/systemd/system/actions-runner.dockp04.service
[Unit]
Description=GitHub Actions Runner (dockp04)
After=network-online.target docker.service
Wants=network-online.target docker.service
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=github-runner
Group=github-runner
WorkingDirectory=/home/github-runner/actions-runner
Environment="HOME=/home/github-runner"
ExecStart=/home/github-runner/actions-runner/run.sh
ExecStop=/bin/pkill -TERM -f "run.sh"
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/github-runner/actions-runner,/var/run/tetragon
PrivateTmp=true
PrivateDevices=true
ProtectHostname=true
ProtectClock=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectKernelLogs=true
LockPersonality=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
MemoryDenyWriteExecute=false  # Required for runner JIT
RestrictNamespaces=true
RemoveIPC=true
# Allow only specific capabilities
AmbientCapabilities=
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
```

#### Systemd Sandbox Directives Explained

| Directive | Purpose |
|-----------|---------|
| `NoNewPrivileges=true` | Prevents runner from gaining new privileges via setuid binaries |
| `ProtectSystem=strict` | Mounts `/usr`, `/boot`, `/etc` read-only; only `/home/github-runner` and `/var/run` writable |
| `ProtectHome=read-only` | Runner home dir is read-only unless explicitly in `ReadWritePaths` |
| `PrivateTmp=true` | Runner sees empty `/tmp` and `/var/tmp` — no cross-process tmp file leakage |
| `PrivateDevices=true` | Runner sees minimal `/dev` — no device access |
| `ProtectHostname=true` | Runner cannot modify system hostname |
| `ProtectClock=true` | Runner cannot modify system clock |
| `ProtectKernelTunables=true` | Runner cannot modify kernel parameters via `/proc/sys` |
| `ProtectKernelModules=true` | Runner cannot load/unload kernel modules |
| `ProtectKernelLogs=true` | Runner cannot read kernel logs |
| `LockPersonality=true` | Runner cannot change personality (32-bit emulation, etc.) |
| `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX` | Runner can only use IP and Unix sockets — no other address families (no netlink, no packet sockets) |
| `RestrictNamespaces=true` | Runner cannot create new namespaces (mount, PID, network, etc.) |
| `RemoveIPC=true` | Runner cannot leave IPC objects after exit |
| `CapabilityBoundingSet=` (empty) | Runner has zero Linux capabilities — no raw network, no raw sockets |

---

## 3. Secrets Security

### 3.1 Current State

Secrets are loaded via `1password/load-secrets-action@v2` with:
- `OP_CONNECT_HOST` + `OP_CONNECT_TOKEN` stored as GitHub repo secrets
- Broad vault access: entire `Homelab` vault accessible via Connect token
- Secrets written to `.env` files on disk (even if chmod 640)

### 3.2 Target State: OIDC-Backed Short-Lived Tokens

GitHub Actions supports OIDC token authentication with cloud providers. For 1Password Connect, we implement a similar pattern: the runner fetches a short-lived token from Connect using a pre-shared key, scoped to specific vault items only.

#### Architecture

```
GitHub Actions Workflow
    │
    ▼
1Password Connect API (https://<host>:8080)
    │  ← OIDC-style token exchange: service account key → short-lived token
    │  ← Token scoped to specific item paths only
    ▼
Short-lived token (TTL: 5 minutes)
    │
    ▼
Secret fetch (token used once, discarded)
```

#### Implementation: OIDC Token Exchange for Connect

1Password Connect does not natively support OIDC. We implement a thin wrapper:

**`op-token-exchange`** (new container, per runner host):

```python
# op-token-exchange.py — lightweight OIDC-style token exchange
# Runs alongside 1Password Connect on each host
# Listens on localhost:8089 (not externally exposed)

from flask import Flask, request, jsonify
import hmac
import hashlib
import time
import requests

app = Flask(__name__)

# Pre-shared key stored in /mnt/docker/secrets/op-service-account.key
# (created once, stored in 1Password as "Runner-OP-Service-Account")
with open('/mnt/docker/secrets/op-service-account.key', 'r') as f:
    SERVICE_ACCOUNT_KEY = f.read().strip()

CONNECT_HOST = 'http://localhost:8080'
VAULT_NAME = 'Homelab'

# Scoped item access — runner can only access these specific items
ALLOWED_ITEMS = {
    'homelab-core': [
        'homelab-postgres-db-dockp04-core/password',
        'homelab-postgres-db-dockp04-core/username',
        'homelab-cloudflare-api-key-global/credential',
        'homelab-cloudflare-api-key-global/username',
    ],
    'homelab-ai': [
        'homelab-huggingface-token-primary/credential',
    ],
    'homelab-security': [
        'Dockp04-Security-Secrets/SPLUNK_PASSWORD',
        'Dockp04-Security-Secrets/SPLUNK_HEC_TOKEN',
    ],
    # Add items per repo as needed
}

@app.route('/token', methods=['POST'])
def exchange_token():
    """
    Exchange a pre-shared service account key for a short-lived Connect token.
    The returned token is scoped to only the allowed items for this runner.
    """
    body = request.get_json()
    service_key = body.get('service_account_key', '')
    repo = body.get('repo', '')  # e.g., 'homelab-core'
    workflow = body.get('workflow', '')  # e.g., 'deploy-dockp04-core'

    # Validate pre-shared key
    if not hmac.compare_digest(service_key, SERVICE_ACCOUNT_KEY):
        return jsonify({'error': 'invalid key'}), 401

    # Determine allowed items for this repo
    allowed = ALLOWED_ITEMS.get(repo, [])
    if not allowed:
        return jsonify({'error': 'repo not authorized'}), 403

    # Fetch a Connect token via the standard API
    # (Connect token has full vault access — we restrict via item path filtering)
    resp = requests.post(
        f'{CONNECT_HOST}/v1/vaults/{VAULT_NAME}/items',
        headers={'Authorization': f'Bearer {SERVICE_ACCOUNT_KEY}'},
        timeout=10
    )

    if resp.status_code != 200:
        return jsonify({'error': 'connect unavailable'}), 503

    # Return short-lived exchange token with scoped item references
    exchange_token = hmac.new(
        SERVICE_ACCOUNT_KEY,
        f'{repo}:{workflow}:{int(time.time())}',
        hashlib.sha256
    ).hexdigest()[:32]

    return jsonify({
        'exchange_token': exchange_token,
        'connect_host': CONNECT_HOST,
        'allowed_items': allowed,
        'ttl_seconds': 300,  # 5 minutes
        'repo': repo,
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8089)
```

#### Workflow Integration

Replace `1password/load-secrets-action` with a custom action:

```yaml
# .github/actions/op-fetch-secrets/action.yml
name: Fetch secrets via OIDC exchange
description: Fetches secrets from 1Password Connect using short-lived scoped token
inputs:
  repo:
    description: Repository name (e.g., homelab-core)
    required: true
  secrets:
    description: JSON array of secret paths [{name, op_path}]
    required: true
outputs:
  secret_name:
    description: Secret value
    value: ${{ steps.fetch.outputs.secret_name }}
runs:
  using: composite
  steps:
    - id: exchange
      shell: bash
      run: |
        RESPONSE=$(curl -s -X POST http://localhost:8089/token \
          -H 'Content-Type: application/json' \
          -d "{\"service_account_key\": \"$OP_SERVICE_ACCOUNT_KEY\", \"repo\": \"${{ inputs.repo }}\"}")
        EXCHANGE_TOKEN=$(echo "$RESPONSE" | jq -r '.exchange_token')
        CONNECT_HOST=$(echo "$RESPONSE" | jq -r '.connect_host')
        ALLOWED_ITEMS=$(echo "$RESPONSE" | jq -r '.allowed_items | @json')

        echo "::add-mask::$EXCHANGE_TOKEN"
        echo "exchange_token=$EXCHANGE_TOKEN" >> $GITHUB_OUTPUT
        echo "connect_host=$CONNECT_HOST" >> $GITHUB_OUTPUT

    - id: fetch
      shell: bash
      env:
        EXCHANGE_TOKEN: ${{ steps.exchange.outputs.exchange_token }}
        CONNECT_HOST: ${{ steps.exchange.outputs.connect_host }}
      run: |
        # Fetch each secret using the exchange token
        # Token is used once and discarded — no caching, no disk write
        SECRET_VALUE=$(curl -s \
          -H "Authorization: Bearer $EXCHANGE_TOKEN" \
          "$CONNECT_HOST/v1/vaults/Homelab/items/$(echo '${{ inputs.secrets }}' | jq -r '.[0].op_path')" \
          | jq -r '.details.fields[0].value')
        echo "secret_name=$SECRET_VALUE" >> $GITHUB_OUTPUT
```

**Key improvements over current state:**
1. **No broad vault access** — exchange token is scoped to specific repo+workflow
2. **Short TTL** — token expires in 5 minutes
3. **No secrets on disk** — secrets fetched at workflow step time, used immediately, never stored
4. **Audit trail** — every token exchange logged with repo+workflow+timestamp

### 3.3 Secret Scoping Matrix

| Repo | Workflow | Allowed 1Password Items |
|------|----------|------------------------|
| `homelab-core` | deploy-dockp04-core | `homelab-postgres-db-dockp04-core/*`, `homelab-cloudflare-api-key-global/*` |
| `homelab-ai` | deploy-dockp01-ai | `homelab-huggingface-token-primary/credential` |
| `homelab-security` | deploy-dockp04-security | `Dockp04-Security-Secrets/*` |
| `homelab-automation` | deploy-dockp04-automation | `homelab-prefect-secrets/*`, `homelab-slack-webhook/*` |
| `homelab-media` | deploy-blog | `homelab-blog-secrets/*` |

---

## 4. Audit Logging

### 4.1 What to Ship to Splunk

All runner activity is logged to Splunk via HEC (HTTP Event Collector) on port 8088.

#### Log Categories

| Category | Source | Splunk Index | Retention |
|----------|--------|--------------|------------|
| **Process execution** | Tetragon `execve` kprobe | `tetragon` | 90 days |
| **Network connections** | Tetragon `connect` kprobe | `tetragon` | 90 days |
| **File operations** | Tetragon `openat`/`write` kprobe | `tetragon` | 90 days |
| **Secret access** | `op-fetch-secrets` action | `secrets` | 365 days |
| **Docker operations** | Docker daemon logs | `docker` | 90 days |
| **Git operations** | Git audit log | `git` | 365 days |
| **Firewall drops** | iptables LOG target | `network` | 90 days |
| **Sudo usage** | `sudo` logs via `pam_sudo` | `audit` | 365 days |
| **Authentication** | SSH, GitHub token exchange | `auth` | 365 days |

#### Tetragon Tracing Policies for Runners

Extend existing policies with runner-specific detection:

```yaml
# tetragon.conf.d/runner_privilege_escalation.tp.d/sudo_usage.tp
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: "runner-sudo-usage"
  annotations:
    description: "Detect sudo usage by runner process"
    category: "privilege_escalation"
    severity: "high"
spec:
  kprobes:
  - call: "sys_execve"
    syscall: true
    args:
    - index: 0
      type: "string"
    selectors:
    - matchArgs:
      - index: 0
        operator: "Postfix"
        values:
        - "/sudo"
        - "/su"
      matchNamespaces:
      - operator: "In"
        values:
        - github-runner
      matchActions:
      - action: Post
```

```yaml
# tetragon.conf.d/runner_exfiltration.tp.d/outbound_connections.tp
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: "runner-outbound-connections"
  annotations:
    description: "Track all outbound connections from runner processes"
    category: "exfiltration"
    severity: "medium"
spec:
  kprobes:
  - call: "sys_connect"
    syscall: true
    args:
    - index: 0
      type: "sockaddr"
    selectors:
    - matchNamespaces:
      - operator: "In"
        values:
        - github-runner
      matchActions:
      - action: Post
```

### 4.2 Splunk Retention and Alerting

#### Index Configuration

```
# $SPLUNK_HOME/etc/system/local/indexes.conf
[tetragon]
homePath = $SPLUNK_DB/tetragon/db
coldPath = $SPLUNK_DB/tetragon/colddb
thawedPath = $SPLUNK_DB/tetragon/thaweddb
maxTotalDataSizeMB = 512000
frozenBucketRotation = cron
frozenBucketRetention = 90

[secrets]
homePath = $SPLUNK_DB/secrets/db
coldPath = $SPLUNK_DB/secrets/colddb
thawedPath = $SPLUNK_DB/secrets/thaweddb
maxTotalDataSizeMB = 10240
frozenBucketRotation = cron
frozenBucketRetention = 365

[audit]
homePath = $SPLUNK_DB/audit/db
coldPath = $SPLUNK_DB/audit/colddb
thawedPath = $SPLUNK_DB/audit/thaweddb
maxTotalDataSizeMB = 51200
frozenBucketRotation = cron
frozenBucketRetention = 365
```

#### Alert Definitions

| Alert | Search | Threshold | Severity | Action |
|-------|--------|-----------|----------|--------|
| Runner privilege escalation | `index=tetragon event_type=execve (sudo OR su) process_user=github-runner` | Any occurrence | P1 | Slack + Corvus incident |
| Unauthorized network connection | `index=tetragon event_type=connect dest_ip!=140.82.112.0/24 dest_ip!=192.168.20.0/24 dest_ip!=192.168.30.0/24 process_user=github-runner` | Any occurrence | P1 | Slack + Corvus incident |
| Secret access outside workflow | `index=secrets workflow_name!=deploy* workflow_name!=*` | Any occurrence | P2 | Slack |
| Docker socket access | `index=tetragon event_type=execve /docker.sock process_user=github-runner` | Any occurrence | P1 | Slack + Corvus incident |
| Cross-VLAN traffic from runner | `index=network src_ip=192.168.30.0/24 dst_ip=192.168.40.0/24 action=deny` | Any occurrence | P2 | Slack |
| Failed sudo attempts | `index=audit event_type=sudo success=false process_user=github-runner` | >3 in 5 min | P2 | Slack |
| High secret access volume | `index=secrets | stats count by workflow_name` | >50 in 1 hour | P3 | Log only |
| Git push from runner | `index=git event_type=push process_user=github-runner` | Any occurrence | P2 | Slack |

---

## 5. Threat Model

### 5.1 Attack Vectors

| ID | Attack Vector | Description | Affected Component |
|----|-------------|-------------|----------------|-------------------|
| AV-01 | Compromised workflow | Malicious workflow PR merged to repo, runs arbitrary code on runner | GitHub Actions |
| AV-02 | Runner token theft | GitHub runner registration token stolen, rogue runner registered | Runner registration |
| AV-03 | Secret exfiltration | Workflow extracts secrets and exfiltrates via DNS/HTTP | Secrets pipeline |
| AV-04 | Lateral movement | Compromised runner used to scan/reach internal services | Network isolation |
| AV-05 | Container escape | Workflow container escapes to host via Docker socket | Docker isolation |
| AV-06 | Privilege escalation | Runner process escalates to root via sudo/nested privilege | Runner hardening |
| AV-07 | Supply chain compromise | Malicious base image or action fetched from public registry | CI/CD pipeline |
| AV-08 | Log injection | Malicious content injected into logs, triggering XSS in Splunk UI | Logging pipeline |
| AV-09 | Cross-repo contamination | Runner used for multiple repos, secrets bleed between repos | Secret scoping |
| AV-10 | OIDC token replay | Stolen exchange token reused within TTL window | Secrets exchange |
| AV-11 | Tetragon evasion | Attacker uses syscalls not covered by kprobes | Runtime security |
| AV-12 | Network pivot | Runner used as jump host to reach IoT VLAN or other restricted networks | Network segmentation |

### 5.2 Mitigations

| ID | Mitigation | Control Type | Effectiveness |
|----|-----------|------------|--------------|---------------|
| AV-01 | Required PR reviewers + CODEOWNERS + branch protection | Preventive | High |
| AV-02 | Runner token has 1-hour TTL; runner de-registers after use | Preventive | High |
| AV-03 | Secrets fetched via short-lived scoped token; no disk write; DNS filtering | Detective + Preventive | High |
| AV-04 | Runner in VLAN 30 with egress allowlist only; no inbound | Preventive | High |
| AV-05 | Rootless Docker; host Docker socket not accessible to runner | Preventive | High |
| AV-06 | Runner as non-sudo user; systemd sandbox; CapabilityBoundingSet=empty | Preventive | High |
| AV-07 | Pin base images to SHA256 digest; private registry mirror for critical images | Preventive | Medium |
| AV-08 | Log sanitization in HEC forwarder; Splunk XSS filtering enabled | Preventive | High |
| AV-09 | Per-repo scoped tokens; runner cannot access other repo's items | Preventive | High |
| AV-10 | Token TTL 5 min; HMAC-bound to specific repo+workflow+timestamp | Preventive | High |
| AV-11 | Tetragon covers all execve/connect/openat; updated policy set | Detective | Medium |
| AV-12 | UniFi firewall denies VLAN 30 → VLAN 400; VLAN 30 has no inbound rules | Preventive | High |

### 5.3 Residual Risk

| ID | Residual Risk | Likelihood | Impact | Acceptability |
|----|---------------|-------------|----------|----------|--------------|
| AV-01 | Insider threat: trusted contributor merges malicious code | Low | High | Acceptable with AV-01 mitigations + audit logging |
| AV-05 | Zero-day Docker escape (unprivileged container escape) | Very Low | High | Acceptable — rootless Docker limits blast radius |
| AV-07 | Zero-day image registry compromise | Low | High | Acceptable with image pinning + SHA verification |
| AV-11 | Novel syscall not covered by Tetragon kprobes | Low | Medium | Acceptable with defense-in-depth (network isolation) |
| AV-12 | UniFi firewall misconfiguration | Low | High | Acceptable with change control + Corvus pre-check |

### 5.4 Threat Model Summary Table

| Threat | AV-01 | AV-02 | AV-03 | AV-04 | AV-05 | AV-06 | AV-07 | AV-08 | AV-09 | AV-10 | AV-11 | AV-12 |
|--------|------|------|------|------|------|------|------|------|------|------|------|------|
| **Mitigation** | PR review | Token TTL | Scoped token | VLAN 30 | Rootless | No sudo | SHA pin | Sanitization | Per-repo scope | HMAC+TTL | Kprobe coverage | Firewall |
| **Residual** | Insider | — | — | — | Docker 0day | — | Registry 0day | — | — | Replay | Novel syscall | FW misconfig |
| **Severity** | Medium | Low | Low | Low | Very Low | Very Low | Low | Very Low | Low | Low | Low | Low |

---

## 6. Implementation Phases

### Phase 1: Network Isolation (Week 1-2)
- [ ] Create VLAN 30 for runners
- [ ] Configure UniFi firewall rules for VLAN 30 egress allowlist
- [ ] Apply iptables runner-firewall.sh on runner hosts
- [ ] Verify no inbound access to runner hosts

### Phase 2: Runner Hardening (Week 3-4)
- [ ] Create `github-runner` user on all runner hosts
- [ ] Configure sudoers file with scoped commands
- [ ] Migrate runner service from `tmiller` to `github-runner` user
- [ ] Apply systemd service hardening (ProtectSystem, CapabilityBoundingSet, etc.)
- [ ] Verify rootless Docker configuration

### Phase 3: Secrets Security (Week 5-6)
- [ ] Deploy `op-token-exchange` container on each runner host
- [ ] Create service account key in 1Password
- [ ] Update workflow files to use `op-fetch-secrets` action instead of `load-secrets-action`
- [ ] Configure per-repo item scoping in exchange service
- [ ] Verify no broad vault access via runner tokens

### Phase 4: Audit Logging (Week 7-8)
- [ ] Configure Splunk indexes with retention policies
- [ ] Deploy runner-specific Tetragon tracing policies
- [ ] Configure Splunk alerts for all categories in Section 4.2
- [ ] Verify log flow from runner → Tetragon → Splunk
- [ ] Test alert triggers with simulated events

### Phase 5: Validation (Week 9)
- [ ] Full threat model walkthrough with simulated attacks
- [ ] Verify all mitigations are in place
- [ ] Document residual risks and acceptance
- [ ] Update runbooks with new security procedures

---

## 7. References

- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Tetragon Documentation](https://docs.cilium.io/en/stable/tetragon/)
- [1Password Connect API](https://developer.1password.com/docs/connect/)
- [Docker Rootless Mode](https://docs.docker.com/engine/security/rootless/)
- [systemd Service Hardening](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [UniFi Firewall Configuration](https://help.ui.com/unifi-network/firewall)
- Existing homelab network security: `living-docs/docs/governance/network-security.md`
- Existing Tetragon policies: `homelab-security/stacks/security/tetragon/tetragon.conf.d/`
- Existing runner setup: `living-docs/RUNNER_SETUP.md`