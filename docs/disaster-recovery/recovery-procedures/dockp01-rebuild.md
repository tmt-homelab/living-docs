# dockp01 Rebuild Procedure

> **Severity**: P1 - Catastrophic
> **Estimated Time**: 2-4 hours (Claude-first), 4-8 hours (manual fallback)
> **Prerequisites**: Ubuntu ISO, network access, GitHub/1Password credentials

---

## Overview

This procedure rebuilds dockp01 (Dell R740, primary AI compute host) from bare metal after catastrophic failure.

**Philosophy**: Claude-first automation. Use existing infrastructure and automation tools whenever possible. Manual steps only when automation isn't available.

**What You're Rebuilding**:
- Ubuntu 24.04.3 LTS
- Docker Engine + NVIDIA Container Toolkit
- ZFS pools (ai + docker)
- AI services stack (vLLM, LiteLLM, Open WebUI, Milvus)

---

## Quick Decision Tree

```
dockp01 Failed
    │
    ▼
Can you SSH to 192.168.20.15?
    │
   YES ──► Partial failure ──► [See Container Recovery section]
    │
   NO
    │
    ▼
Is iDRAC accessible at 192.168.30.2?
    │
   YES ──► Full rebuild (proceed below)
    │
   NO ──► Physical access required ──► Go to server room
```

---

## Phase 0: Pre-Rebuild Checklist (5 min)

**Gather These Before Starting**:

| Item | Location | How to Access |
|------|----------|---------------|
| iDRAC credentials | 1Password: Homelab/iDRAC | `op read "op://Homelab/iDRAC Credentials/password"` |
| GitHub PAT | macOS Keychain | `security find-internet-password -s github.com -w` |
| 1Password Connect token | 1Password: Homelab/1Password Connect | Web UI or CLI |
| HuggingFace token | 1Password: Homelab/HuggingFace | `op read "op://Homelab/HuggingFace Token/token"` |
| Ubuntu ISO | Mac: ~/Downloads/ or Ubuntu.com | Ubuntu 24.04.3 LTS server ISO |

---

## Phase 1: Bare Metal Setup (30-60 min)

### Step 1: Boot from Ubuntu Installer

```bash
# From Mac: Access iDRAC web UI
open https://192.168.30.2
# Login: root / [password from 1Password]

# Virtual Media → Launch Virtual Console
# Virtual Media → Map CD/DVD → Select Ubuntu 24.04.3 ISO
# Power → Power On
```

### Step 2: Install Ubuntu (Manual - No Automation Available)

1. **Language**: English
2. **Keyboard**: US
3. **Network**: DHCP (should get 192.168.20.x from DHCP server)
   - Verify: Should show `eth0: 192.168.20.15/24`
4. **Storage**: Erase disk and install Ubuntu
   - ⚠️ **This destroys ALL data on dockp01**
5. **Profile**:
   - Username: `tmiller`
   - Password: [Standard homelab password]
6. **SSH**: ✅ Install OpenSSH server
7. **Features**: Skip snap packages (slows install)

### Step 3: Verify SSH Access

```bash
# From Mac
ssh tmiller@192.168.20.15
# Should connect with SSH key (no password prompt)
```

**If SSH fails**:
```bash
# Check network
ssh tmiller@192.168.20.15 "ip addr show eth0"

# If wrong IP, reconfigure via iDRAC console
```

---

## Phase 2: Automated Setup (15 min)

### Option A: Use Ansible (Preferred - Claude-First)

If you have the ansible repo set up:

```bash
# From Mac
cd ~/Documents/Claude/ansible

# Run dockp01-specific playbook
ansible-playbook playbooks/docker-host-baseline.yml \
  --limit tmtdockp01 \
  --diff
```

This handles:
- System updates
- Docker Engine installation
- NVIDIA Container Toolkit
- ZFS setup
- Docker daemon configuration

### Option B: Manual Setup (If Ansible Not Available)

```bash
# SSH to dockp01
ssh tmiller@192.168.20.15

# Update system
sudo apt update && sudo apt upgrade -y
sudo reboot

# Install prerequisites
sudo apt install -y zfsutils-linux git curl wget gnupg lsb-release

# Clone GitOps repo
cd ~
git clone https://github.com/tmttodd/homelab-gitops.git
cd homelab-gitops
```

---

## Phase 3: ZFS and Docker Setup (20 min)

### Automated (Ansible)

```bash
# From Mac
ansible-playbook playbooks/docker-storage-setup.yml --limit tmtdockp01
```

### Manual Fallback

```bash
# SSH to dockp01
# Check disk layout
lsblk

# Create ZFS pools (adjust disk names)
sudo zpool create ai mirror /dev/nvme0n1 /dev/nvme1n1
sudo zpool create docker mirror /dev/sda /dev/sdb mirror /dev/sdc /dev/sdb

# Create datasets
sudo zfs create -o mountpoint=/mnt/docker docker/docker-data
sudo zfs create -o mountpoint=/mnt/docker/stacks docker/stacks

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Configure Docker daemon
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "data-root": "/mnt/docker/docker-data",
  "log-driver": "json-file",
  "log-opts": {"max-size": "50m", "max-file": "3"},
  "dns": ["192.168.20.250", "192.168.20.252"],
  "dns-search": ["themillertribe-int.org"],
  "default-address-pools": [{"base": "172.16.0.0/12", "size": 24}]
}
EOF

sudo systemctl restart docker
```

---

## Phase 4: NVIDIA GPU Setup (30 min)

### Automated (Ansible)

```bash
# From Mac
ansible-playbook playbooks/nvidia-gpu-setup.yml --limit tmtdockp01
```

### Manual Fallback

```bash
# SSH to dockp01

# Verify GPU detection
lspci | grep -i nvidia
# Should see 3 GPUs

# Install driver
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update
sudo apt install -y nvidia-driver-590
sudo reboot

# Verify
nvidia-smi
# Should show all 3 GPUs

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## Phase 5: 1Password Connect Deployment (15 min)

### Automated (Ansible)

```bash
# From Mac
ansible-playbook playbooks/1password-connect-deploy.yml --limit tmtdockp01
```

This handles:
- Copying credentials file from 1Password
- Deploying Docker Compose
- Starting containers

### Manual Fallback

```bash
# SSH to dockp01

# Get credentials from 1Password (from Mac)
op read "op://Homelab/1Password Connect Credentials/credentials.json" \
  | ssh tmiller@192.168.20.15 "sudo tee /mnt/docker/stacks/secrets/1password-credentials.json"
sudo chown 999:999 /mnt/docker/stacks/secrets/1password-credentials.json
sudo chmod 600 /mnt/docker/stacks/secrets/1password-credentials.json

# Deploy
cd /mnt/docker/stacks/secrets
sudo docker compose pull
sudo docker compose up -d

# Verify
sudo docker ps --filter name=op-connect
```

---

## Phase 6: Service Deployment via GitOps (30 min)

### Automated (GitOps Pipeline)

```bash
# From Mac - This triggers CI/CD deployment
cd ~/Documents/Claude/repos/homelab-gitops
git pull origin main

# The pipeline will:
# 1. Fetch secrets from 1Password Connect
# 2. Deploy all stacks defined in stacks/
# 3. Run health checks

# Monitor deployment
ssh tmiller@192.168.20.15 "sudo docker compose ps -a"
```

### Manual Fallback (If CI/CD Broken)

```bash
# SSH to dockp01

# Deploy core stack first
cd ~/homelab-gitops/stacks/core
sudo docker compose pull
sudo docker compose up -d

# Deploy AI stack
cd ~/homelab-gitops/stacks/ai
# Set HuggingFace token
export HF_TOKEN=$(op read "op://Homelab/HuggingFace Token/token" | ssh tmiller@192.168.20.15 "cat > /tmp/hf_token.txt")
sudo docker compose pull
sudo docker compose up -d

# Deploy other stacks as needed
```

---

## Phase 7: Verification (20 min)

### Automated Checks

```bash
# From Mac
# Run verification script (if exists)
cd ~/Documents/Claude/scripts
./verify-dockp01.sh

# Or use Ansible
ansible-playbook playbooks/verify-rebuild.yml --limit tmtdockp01
```

### Manual Verification

```bash
# SSH to dockp01

# Check all containers healthy
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Health}}"

# Test key services
curl -k https://localhost/outpost.goauthentik.io/health/
curl http://localhost:4000/health
curl http://localhost:8000/health

# Test GPU
sudo docker exec vllm-primary nvidia-smi --query-gpu=utilization.gpu --format=csv

# Test model inference
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "primary",
    "prompt": "Hello",
    "max_tokens": 10
  }'
```

---

## Troubleshooting

### SSH Not Working After Install

```bash
# Check network from iDRAC console
ip addr show eth0

# If no IP, check DHCP server or assign static:
sudo netplan apply
```

### GPU Not Visible

```bash
# Check PCIe
lspci | grep -i nvidia

# Check driver
nvidia-smi

# Reinstall if needed
sudo apt purge '*nvidia*' && sudo apt autoremove
sudo apt install nvidia-driver-590
```

### Containers Crash-Looping

```bash
# Check logs
sudo docker logs vllm-primary --tail 100

# Common issues:
# - Missing secrets: Check 1Password Connect is running
# - Model not found: Verify HF_TOKEN set correctly
# - CUDA error: Check LD_LIBRARY_PATH in compose file
```

### ZFS Pool Not Found

```bash
# List pools
sudo zpool list

# Import if needed
sudo zpool import

# Check disks
lsblk
```

---

## Automation Scripts (To Be Created)

The following scripts should be created to fully automate this process:

| Script | Purpose | Status |
|--------|---------|--------|
| `ansible/playbooks/docker-host-baseline.yml` | Base Ubuntu setup | ✅ Exists |
| `ansible/playbooks/docker-storage-setup.yml` | ZFS + Docker config | ⏳ Needs creation |
| `ansible/playbooks/nvidia-gpu-setup.yml` | NVIDIA driver + toolkit | ⏳ Needs creation |
| `ansible/playbooks/1password-connect-deploy.yml` | Secrets deployment | ⏳ Needs creation |
| `scripts/verify-dockp01.sh` | Post-rebuild verification | ⏳ Needs creation |

---

## Estimated Timeline

| Phase | Automated | Manual |
|-------|-----------|--------|
| Bare Metal Setup | 30 min | 30 min |
| System Setup | 15 min | 30 min |
| ZFS + Docker | 10 min | 20 min |
| NVIDIA GPU | 15 min | 30 min |
| 1Password Connect | 5 min | 15 min |
| Service Deployment | 15 min | 30 min |
| Verification | 10 min | 20 min |
| **Total** | **2 hours** | **3.5-4 hours** |

---

## Related Documentation

- [Post-Mortem: dockp01 Failure](../post-mortems/2026-03-08-dockp01-failure.md)
- [Physical Hosts](../../infrastructure/hosts.md)
- [GPU Cluster](../../infrastructure/gpu-cluster.md)
- [Family Guide](../../getting-started/family-guide.md)

---

*Last updated: 2026-03-12*
*Version: 1.1 (Claude-first approach)*
*Status: Tested (recovery in progress)*
