

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for standard HA) |
| **Tolerable outage** | "unplanned outage acceptable for ≤ 1 hour" (CMDB critical: false) |
| **Blast radius if down** | NemoClaw triage fails over to LiteLLM "chat" fallback; Ops playbook execution degrades to human review only |
| **Recovery time today** | auto-restart (Docker `unless-stopped`), but 15m cold start |
| **Owner** | `phase-1.4-bulk-backfill` (automated) / homelab-ai team |

## What this service actually does

Serves the `Qwen3.6-35B-A3B-FP8` model specifically for operational triage logic. NemoClaw invokes this service when standard runbooks fail ("playbook miss"). It performs structured reasoning (`enable_thinking`) and tool calling (`enable-auto-tool-choice`) to diagnose incidents on `tmtdockp02`.

Other fleet services access it via HTTP API at `http://192.168.20.16:8003` (mapped from container `8000`). LiteLLM on `tmtdockp01` routes `ops-brain` group traffic here. It is NOT used for general user chat or image generation, despite the model's multimodal capabilities; those are reserved for `vllm-reason` (GPU 2) or `comfyui` (GPU 1).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai-gpu2/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.20.0-cu130@sha256:77797441eae630c2e79eefa03957b3d61a278670f2a9928d64ce102e7a0790cc` |
| **Pinning policy** | Digest pinned (rollback digest: `sha256:2ccff44e...`) |
| **Resource caps** | GPU 0 only (`NVIDIA_VISIBLE_DEVICES=0`); 48GB VRAM; 88% util cap |
| **Volumes** | `/mnt/docker/ai/models` (ro, ZFS); `/mnt/docker/ai/cache/huggingface` (rw) |
| **Networks** | `ai-gpu2` (bridge) |
| **Secrets** | None (credentials not required for inference) |
| **Healthcheck** | `curl -f http://127.0.0.1:8000/health`; 30s interval, 10s timeout, 3 retries |

### Configuration shape

All configuration via CLI flags. Environment variables control CUDA ordering and threading (`OMP_NUM_THREADS=4`). No external YAML/JSON config files mounted. Model path is hardcoded to `/mnt/models/vllm/Qwen3.6-35B-A3B-FP8`.

## Dependencies

### Hard (service cannot start or operate without these)
- **GPU 0 (RTX PRO 5000)** — Specific hardware binding; service crashes if device missing.
- **ZFS dataset `/mnt/docker/ai/models`** — Read-only mount required for weights.
- **Host network access** — LiteLLM routes traffic via host IP `192.168.20.16`.

### Soft (degrade if these are down, but service still functional)
- **Huggingface Cache** — If `/mnt/docker/ai/cache/huggingface` is full/unwritable, new tokenizers may fail to load, but existing model runs.

### Reverse (services that depend on THIS service)
- **NemoClaw** — Primary consumer for triage. Breaks triage logic if down.
- **LiteLLM (tmtdockp01)** — Routing layer. Fails to route `ops-brain` requests if down.

## State & persistence

- **Database tables:** None.
- **Filesystem state:** `/mnt/docker/ai/cache/huggingface` stores downloaded tokenizers/configs. Read-only model weights on `/mnt/docker/ai/models`.
- **In-memory state:** KV cache (8GB budget) lost on restart. Conversation history not persisted by service.
- **External state:** None.

## Behavior baselines

| Metric | Steady-state | Alert threshold |