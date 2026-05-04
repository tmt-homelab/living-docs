

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical per CMDB) |
| **Blast radius if down** | `comfy-bridge` API 500s on generation requests; Direct UI (8188) inaccessible |
| **Recovery time today** | Auto-restart (`unless-stopped`) + manual GPU reset if OOM lockup |
| **Owner** | `claude-code` (registered_by) / `?` (human steward) |

## What this service actually does

Hosts FLUX.2 image generation inference on GPU 1 (RTX PRO 6000 Blackwell, 98GB VRAM). Serves the ComfyUI API for direct workflow execution and acts as the backend for `comfy-bridge` (programmatic generation queue).

Other fleet services consume this via HTTP API (port 8188) or via the `comfy-bridge` proxy (port 8189). It is NOT used for text inference (Gemma 4 moved to GPU 2 on `ai-gpu2` stack) or video generation. Models are cached in VRAM via `--highvram` to maximize throughput; persistent model storage is split between local NVMe (hot diffusion models) and NFS (cold custom nodes/LoRAs).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp02-comfyui/docker-compose.yml` |
| **Image** | `ghcr.io/tmt-homelab/comfyui:latest` |
| **Pinning policy** | Tag-floating (`:latest`). Auto-update via GH Actions daily at 06:00 UTC |
| **Resource caps** | GPU: `device_ids: ['1']` (RTX PRO 6000); Memory: Unbounded (VRAM dependent) |
| **Volumes** | Local NVMe (`/mnt/docker/data/comfyui`), Local NVMe Models (`/mnt/docker/ai/models/comfyui`), NFS (`/mnt/models/comfyui`), Named (`comfy_bridge_queue`) |
| **Networks** | `default`, `secrets_default` |
| **Secrets** | `${HF_TOKEN}`, `${BRIDGE_API_KEY}`, `${ADMIN_API_TOKEN}` (via env) |
| **Healthcheck** | `curl -f http://127.0.0.1:8188/` (30s interval, 120s start_period) |

### Configuration shape

Configuration is driven entirely by `CLI_ARGS` environment variable passed to the entrypoint.
- `--listen 0.0.0.0`: Enables external binding.
- `--highvram`: Keeps all models in VRAM (requires 98GB).
- `--cache-lru 2`: Limits model cache to 2 slots to free RAM for host OS.
- Startup wrapper (`./startup_wrapper.sh`) installs FluxText/TextOverlay deps before ComfyUI PID 1 starts.

## Dependencies

### Hard (service cannot start or operate without these)
- **NVIDIA Driver on Host** — GPU binding (`device_ids: ['1']`) requires kernel modules loaded on `tmtdockp02`.
- **Local NVMe Mount** — `/mnt/docker/ai/models/comfyui` required for diffusion models (critical for cold start performance).

### Soft (degrade if these are down, but service still functional)
- **NFS Share** — `/mnt/models/comfyui` (LoRAs, ControlNet). Service starts but missing custom nodes/LoRAs on UI.
- **`comfy-bridge`** — If bridge is down, programmatic API queueing fails (direct UI still works).

### Reverse (services that depend on THIS service)
- **`comfy-bridge`** — Polls `http://comfyui:8188` for job completion. If `comfyui` dies, bridge queues accumulate or fail.

## State & persistence

- **Database tables / schemas**: None (ComfyUI native). `comfy-bridge` uses SQLite in `comfy_bridge_queue` volume (`/tmp` inside container).
- **Filesystem state**:
    - **Writable**: `/mnt/docker/data/comfyui/output` (Generated images), `/mnt/docker/data/comfyui/input` (Uploaded workflows), `/mnt/docker/data/comfyui/temp` (Scratch).
    - **Read-Only**: `/mnt/docker/ai/models/comfyui/*` (Diffusion/Text/Vae/Checkpoints), `/mnt/models/comfyui/*` (LoRAs/ControlNet/Custom Nodes).
    - **Growth Rate**: Output directory grows based on generation volume; estimated 10GB/week retention policy needed.
- **In-memory state**: VRAM model cache (lost on restart). HF cache (`/mnt/docker/data/comfyui/hf_cache`) persists locally.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 5% (GPU offload) | > 50% sustained | N/A |
| Memory | 98GB VRAM usage | > 95% VRAM | OOM kills process / container restarts |
| Disk I/O | Bursty (Model load) | NFS latency > 500ms | Model load hangs on cold start |
| Network | Low (Control) | > 100Mbps | N/A |
| GPU (if applicable) | 0% (Idle) / 100% (Gen) | Temp > 85°C | Throttling / Driver hang |
| Request latency p50 / p95 / p99 | 5s / 15s / 30s | > 60s | Queue backlog grows |
| Request rate | Variable | > 1 req/min sustained | Queue saturation |

## Failure modes

- **Symptom**: Container restarts loop / `comfy-bridge` returns 503.
    - **Root cause**: VRAM OOM during large batch generation or model loading.
    - **Mitigation**: `docker logs comfyui`, reduce `--cache-lru` or remove large LoRAs.
    - **Prevention**: Enforce model size limits on input; monitor `nvidia-smi` history.
- **Symptom**: UI loads but "Model not found" errors for specific workflows.
    - **Root cause**: NFS share `/mnt/models/comfyui` disconnected or permissions drift.
    - **Mitigation**: Remount NFS, check `showmount -e`.
    - **Prevention**: NFS health check in host monitoring.
- **Symptom**: `comfy-bridge` queue stalls.
    - **Root cause**: SQLite DB lock on `comfy_bridge_queue` volume or `comfyui` healthcheck failing.
    - **Mitigation**: Restart `comfy-bridge`, check `/tmp` volume permissions.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (Single-instance). GPU binding prevents horizontal scaling.
- **Coordination requirements**: None. Stateless regarding workflow state (stateful only during execution).
- **State sharing across replicas**: N/A. Models are shared via NFS read-only, but inference context is isolated.
- **Hardware bindings**:
    - **GPU**: Strictly bound to `device_ids: ['1']` (RTX PRO 6000). Cannot run on GPU 0 or other hosts without modifying `docker-compose.yml` and `NVIDIA_VISIBLE_DEVICES`.
    - **Host**: Bound to `tmtdockp02` via NFS mount paths and local NVMe paths (`/mnt/docker/...`).
- **Network constraints**: Port 8188 must be unique on `tmtdockp02`. Requires `secrets_default` network for `comfy-bridge` communication.
- **Cluster size constraints**: N/A.
- **Migration cost**: High. Moving to a new host requires:
    1.  Replicating local NVMe model cache (`/mnt/docker/ai/models/comfyui`).
   