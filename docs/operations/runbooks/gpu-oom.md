# GPU OOM (Out of Memory) Runbook

> **Purpose**: Resolve GPU memory exhaustion on vLLM containers
> **Severity**: P2 - Service Degraded
> **Agent**: Responder

---

## Symptoms

- vLLM container crash-looping
- Error: `CUDA out of memory` or `CUDA error: out of memory`
- Container exits with code 137 (OOMKilled)
- `nvidia-smi` shows 100% VRAM usage before crash
- LiteLLM returns 502 errors (upstream unavailable)

---

## Immediate Response (5 minutes)

### Step 1: Confirm GPU OOM

```bash
# Check container status
sudo docker ps --filter name=vllm

# Check recent logs
sudo docker logs vllm-primary --tail 50 | grep -i "memory\|error\|oom"

# Check GPU state
nvidia-smi
```

**Expected**: GPU VRAM at 95-100%, container restarting or exited

### Step 2: Restart Container

```bash
# Stop any restarting container
sudo docker stop vllm-primary

# Clear any zombie processes
sudo pkill -9 -f vllm  # Only if container won't stop

# Start fresh
sudo docker start vllm-primary

# Monitor startup
sudo docker logs vllm-primary --follow
```

**Wait 3-5 minutes** for vLLM to initialize (torch.compile takes time on first boot)

### Step 3: Verify Recovery

```bash
# Check container healthy
sudo docker ps --filter name=vllm-primary

# Test inference
curl http://localhost:8000/v1/models

# Check GPU usage stabilized
nvidia-smi
```

**Expected**: Container `Up`, GPU usage 85-95% (stable)

---

## If Restart Doesn't Work

### Step 4: Check for Root Cause

```bash
# Full log review
sudo docker logs vllm-primary --since 1h | tail -200

# Look for patterns:
# - "CUDA out of memory" during request handling
# - "shm_broadcast" timeout (network issue, not OOM)
# - "torch.compile" failure (version mismatch)

# Check system memory
free -h

# Check for zombie vLLM processes
ps aux | grep vllm | grep -v grep
```

### Step 5: Reduce Memory Pressure

**Option A: Reduce max batch size**

Edit `/mnt/docker/stacks/ai/docker-compose.yml`:

```yaml
environment:
  - VLLM_MAX_MODEL_LEN=131072  # Reduce from 262144
  - VLLM_GPU_MEMORY_UTILIZATION=0.85  # Reduce from 0.95
```

Then:
```bash
sudo docker compose -f /mnt/docker/stacks/ai/docker-compose.yml up -d vllm-primary
```

**Option B: Clear other GPU workloads**

```bash
# Stop non-essential GPU containers
sudo docker stop vllm-embed  # If running on same GPU

# Verify GPU freed
nvidia-smi
```

### Step 6: Check CUDA Compatibility

If error mentions CUDA version mismatch:

```bash
# Check driver version
nvidia-smi --query-gpu=driver_version --format=csv

# Should be 590.48.01 or newer

# Check vLLM environment
sudo docker exec vllm-primary env | grep LD_LIBRARY_PATH

# Should include:
# LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/cuda/lib64
```

**Fix**: Update compose file with correct `LD_LIBRARY_PATH`

---

## Prevention

### Configure Proper Memory Limits

In `docker-compose.yml`:

```yaml
services:
  vllm-primary:
    environment:
      - VLLM_GPU_MEMORY_UTILIZATION=0.90  # Leave 10% headroom
      - VLLM_MAX_MODEL_LEN=131072  # Match expected context
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 2  # TP=2
              capabilities: [gpu]
```

### Monitor GPU Usage

```bash
# Continuous monitoring
watch -n 5 'nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv'
```

**Alert thresholds**:
- Warning: VRAM > 90% for >10 minutes
- Critical: VRAM > 95% or OOM errors

### Set Up Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 300s  # 5 min for torch.compile
```

---

## dockp01 Specific Notes

**GPU Topology**:
- GPU 0: RTX PRO 6000 (98 GB) — TP=2 partner
- GPU 1: RTX PRO 4500 (32 GB) — Embedding/reranking (NOT used for primary)
- GPU 2: RTX PRO 6000 (98 GB) — TP=2 partner

**Critical**: Primary model uses GPUs 0 and 2, NOT 0 and 1!

```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=0,2  # NOT 0,1
```

If GPU 1 is also running workloads, ensure they don't conflict.

---

## dockp02 Specific Notes

**GPU Topology**:
- GPU 0: RTX PRO 5000 (48 GB) — Default model (standalone)
- GPU 1: RTX PRO 6000 (98 GB) — Coder TP=2 partner
- GPU 2: RTX PRO 6000 (98 GB) — Coder TP=2 partner

**Default model** fits comfortably on 48 GB GPU. OOM unlikely unless:
- `max_model_len` set too high
- Batch size too large
- Memory leak in container

---

## Escalation

**After 2 restart attempts fail**:

1. **STOP** all further restart attempts
2. **Document** what was tried and observed
3. **Escalate** to Todd with:
   - Full log output (last 200 lines)
   - `nvidia-smi` output
   - Docker compose config
   - Driver version

**Possible root causes requiring investigation**:
- CUDA driver mismatch
- vLLM version incompatibility
- Model download corruption
- Hardware GPU failure

---

## Related Documentation

- [GPU Cluster](../../infrastructure/gpu-cluster.md) — GPU allocation details
- [Physical Hosts](../../infrastructure/hosts.md) — Server specifications
- [Container Health](container-health.md) — General health checks

---

*Last updated: 2026-03-12*
*Version: 1.0*
