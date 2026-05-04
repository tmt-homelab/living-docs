

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for general HA) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical per CMDB, but blocks advanced triage) |
| **Blast radius if down** | LiteLLM `reason` group fails over to `chat` (Qwen3.5-122B on dockp01) → slower reasoning, higher token cost. NemoClaw escalations degrade to Tier 2. |
| **Recovery time today** | Auto-restart (`unless-stopped`), but model load requires 15m (`start_period: 900s`). Manual intervention required for GPU faults. |
| **Owner** | Homelab AI Team (registered by: `phase-1.4-bulk-backfill`) |

## What this service actually does

Runs the Qwen3.6-27B-FP8 model for structured reasoning and triage tasks. It is the primary backend for the LiteLLM `reason` group on `tmtdockp01`.

- Primary purpose: Execute complex reasoning chains (27B params, FP8 quantized) with tool choice (`qwen3_xml`) and reasoning parser (`qwen3`). Supports VLM inputs (dashboard screenshots).
- How fleet uses it: HTTP API (`:8000`) routed via LiteLLM. Consumers include NemoClaw (Triage) and internal AI assistants.
- What it is NOT used for: General chat (handled by `vllm-chat` on dockp01), Ops Brain triage (handled by `vllm-ops-brain` on GPU 0 same host).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai-gpu2/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.20.0-cu130@sha256:77797441eae630c2e79eefa03957b3d61a278670f2a9928d64ce102e7a0790cc` |
| **Pinning policy** | Digest pinned (rollback available via `sha256:2ccff44e7b60ed43093004af99b57ae49855c9d49c411c6707807a49a6eb0e8e`) |
| **Resource caps** | GPU 2 (RTX PRO 6000, 98GB). `--gpu-memory-utilization 0.92`. `--max-num-seqs 2`. |
| **Volumes** | `/mnt/docker/ai/models:/mnt/models:ro` (ZFS), `/mnt/docker/ai/cache/huggingface:/root/.cache/huggingface` (RW) |
| **Networks** | `ai-gpu2` (bridge). Host IP `192.168.20.16` exposed on port 8000. |
| **Secrets** | None (credentials baked into model repo or env). |
| **Healthcheck** | `curl -f http://127.0.0.1:8000/health` (30s interval, 10s timeout, 3 retries, 900s start_period). |

### Configuration shape

CLI-driven configuration via Docker `command`. No external YAML config file.
- Model path hardcoded: `/mnt/models/vllm/Qwen3.6-27B-FP8`.
- Quantization: `fp8` (weights + KV cache).
- Context: `--max-model-len 262144` (configured), but baseline usage capped at 32K for concurrency.
- Envs: `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `NVIDIA_VISIBLE_DEVICES=2`.

## Dependencies

### Hard (service cannot start or operate without these)
- **Host `tmtdockp02`** — Physical host with NVIDIA RTX PRO 6000 (GPU 2).
- **ZFS Mount `/mnt/docker/ai/models`** — Contains model weights. If missing/unmounted, container fails at startup.
- **NVIDIA Container Toolkit** — Required for `runtime: nvidia`.

### Soft (degrade if these are down, but service still functional)
- **LiteLLM (`tmtdockp01`)** — No traffic received if router is down, but service remains healthy.
- **HuggingFace Cache** — RW volume. If full, new model downloads fail, but existing models work.

### Reverse (services that depend on THIS service)
- **LiteLLM** — Routes `reason` group traffic. Breaks if this service is unhealthy; triggers failover to dockp0