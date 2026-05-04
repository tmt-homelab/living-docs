

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope) |
| **Tolerable outage** | 30 mins (model load time dominates recovery) |
| **Blast radius if down** | LiteLLM `chat` route fails → OpenWebUI `qwen35-122b` unavailable; fallback to `reason`/`code` models only |
| **Recovery time today** | Auto-restart (`unless-stopped`) + ~8m model load |
| **Owner** | SRE-Fleet-Redesign (phase-1.4-bulk-backfill) |

## What this service actually does

Hosts the primary 122B MoE chat model (`Qwen3.5-122B-A10B-FP8`) via vLLM inference engine. Exposes OpenAI-compatible chat API on port 8000. Used by LiteLLM as the `chat` backend for high-complexity reasoning and tool calling.

Consumers connect via `ai-inference` network. It is NOT used for embeddings (`vllm-embed`), reranking (`vllm-rerank`), or image generation. The service performs Expert Parallel (EP=2) across two specific GPUs (0 and 2), skipping the embedding GPU (1).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.20.0-cu130@sha256:77797441eae630c2e79eefa03957b3d61a278670f2a9928d64ce102e7a0790cc` |
| **Pinning policy** | Digest pinned (rollback digest available in comment) |
| **Resource caps** | 2× RTX PRO 6000 (98GB VRAM each), `gpu-memory-utilization 0.92`, `OMP_NUM_THREADS=4` |
| **Volumes** | `/mnt/docker/ai/models` (ro), `/mnt/docker/ai/cache/huggingface` |
| **Networks** | `ai-inference` (internal), `ai-services` (via LiteLLM proxy) |
| **Secrets** | None (env vars injected via host/compose, no 1Password items in record) |
| **Healthcheck** | `curl -f http://127.0.0.1:8000/health`, 30s interval, 900s start_period |

### Configuration shape

Environment defines GPU mapping (`NVIDIA_VISIBLE_DEVICES=0,2`) and CUDA compatibility flags. Command line invokes vLLM with FP8 quantization, Expert Parallelism (`--enable-expert-parallel`), and speculative decoding (`qwen3_next_mtp`). Configuration is static at container start; no hot-reload for model weights.

## Dependencies

### Hard
- **Host GPU Drivers**: Requires NVIDIA driver 590+ (host `tmtdockp01`).
- **ZFS Model Store**: `/mnt/docker/ai/models` must be mounted and readable.
- **vLLM Runtime**: `runtime: nvidia` required in Docker daemon.

### Soft
- **LiteLLM**: Traffic routing (if LiteLLM down, service is healthy but unused).
- **OpenWebUI**: Client UI (if down, no user-facing impact on inference capacity).

### Reverse
- **litellm**: Routes `chat` group requests here. Breaks full chat capability.
- **openwebui**: Primary model for `norbit` tier. Breaks complex reasoning features.

## State & persistence

- **Database tables**: None.
- **Filesystem state**: `/mnt/docker/ai/cache/huggingface` (downloaded weights, grows ~100GB over time). Models at `/mnt/docker/ai/models` are read-only ZFS snapshots.
- **In-memory state**: KV cache in VRAM (lost on restart). Context window state lost.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 4 threads (OMP) | N/A | N/A |
| Memory | ? (Container limits not set) | ? | OOM killer if >4G (host swap) |
| Disk I/O | Low (read model weights once) | N/A | N/A |
| Network | 10Gbps internal | ? | N/A |
| GPU (VRAM) | 92% utilized | >95% | OOM → engine crash |
| Request latency p50 | ? | p95 >10s | Queue depth increases |
| Request rate | ? | ? | Context window fills, eviction |

## Failure modes

- **OOM (VRAM)**:
  - **Symptom**: Container restarts, logs show `CUDA out of memory`.
  - **Root cause**: `gpu-memory-utilization` too high for KV cache demand (`--max-model-len 262144`).
  - **Mitigation**: Lower `--max-model-len` or reduce `--gpu-memory-utilization`.
  - **Prevention**: Monitor VRAM headroom; fallback to INT4 single-GPU config if persistent.

- **EP Communication Error**:
  - **Symptom**: Engine hangs, high latency, NCCL errors in logs.
  - **Root cause**: Non-contiguous GPUs (0, 2) causing cross-GPU communication overhead.
  - **Mitigation**: Restart container; if persistent, disable `--enable-expert-parallel`.
  - **Prevention**: Validate benchmarks (p95 TTFT) before promoting to prod.

- **Speculative Decoding Crash**:
  - **Symptom**: EngineCore crash on startup (known in v0.19.1).
  - **Root cause**: Bug in `qwen3_next_mtp` implementation.
  - **Mitigation**: Ensure image tag is v0.20.0+.
  - **Prevention**: Pin digest to v0.20.0 rollback digest if needed.

## HA constraints (input to fleet-reliability design)

- **Replicable**: No (Single instance).
- **Coordination requirements**: None (Stateless compute, but stateful GPU binding).
- **State sharing across replicas**: Not applicable (Cannot run replica on different hardware without model reload).
- **Hardware bindings**:
  - **Host**: `tmtdockp01` (PCI bus IDs 3B:00.0 and D8:00.0).
  - **GPUs**: RTX PRO 6000 Blackwell Max-Q (98GB).
  - **Topology**: GPUs 0 and 2 are non-contiguous (skipping GPU 1). EP=2 requires validation on this topology.
  - **Drivers**: NVIDIA driver 590+ required.
- **Network constraints**: Port 8000 unique. Must be reachable by `litellm` on `ai-inference` network.
- **Cluster size constraints**: Fixed to 1 replica due to GPU topology and ZFS mount exclusivity.
- **Migration cost**: High.
  - Moving to another host requires identical GPU topology (2× 98GB Blackwell).
  - Fallback option: INT4 quantization on single GPU (GPU 0 only) reduces capacity by ~50% but increases availability.
  - Model weights must be synced to new host ZFS pool.
- **Scaling limits**: Cannot scale horizontally without additional `tmtdockp01`-class nodes.

## Operational history

### Recent incidents (last 90 days)
- `2026-04-12` — Architect fleet redesign validation (EP=2 benchmarking).
- `2026-05-01` — CMDB bulk backfill registration.

### Recurring drift / chronic issues
- **EP Stability**: Non-contiguous