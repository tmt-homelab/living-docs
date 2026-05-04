

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance hardware-bound) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 1 hour (non-critical per CMDB) |
| **Blast radius if down** | Open WebUI RAG search fails (no embeddings); LiteLLM routes to error |
| **Recovery time today** | Auto-restart (`unless-stopped`) |
| **Owner** | AI Stack Maintainer (registered by `claude-code`) |

## What this service actually does

Generates dense vector embeddings for RAG context using `Qwen3-VL-Embedding-8B` FP8 quantized. Exposes an OpenAI-compatible API on port 8001 for embedding requests.

Consumed by `litellm` (upstream routing target) and `openwebui` (RAG pipeline ingestion/search). Used strictly for vectorization (`--runner pooling`); NOT used for text generation, chat, or reranking (handled by `vllm-chat` and `vllm-rerank` respectively).

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.18.1-cu130` (Tag-pinned; v0.19.1 rolled back due to memory regression) |
| **Pinning policy** | Tag-pinned (v0.18.1) to avoid v0.19.1 pooling memory regression (29GB vs 14.4GB cap) |
| **Resource caps** | GPU 1 (AF:00.0) only; `--gpu-memory-utilization 0.45` (14.4GB cap on 32GB card) |
| **Volumes** | `/mnt/docker/ai/models` (RO), `/mnt/docker/ai/cache/huggingface` (RW) |
| **Networks** | `ai-inference` (internal only, exposed via `litellm`) |
| **Secrets** | None (auth handled by `litellm` upstream) |
| **Healthcheck** | `curl -f http://127.0.0.1:8001/health` (30s interval, 120s start period) |

### Configuration shape

Env vars set CUDA device order and visibility (`NVIDIA_VISIBLE_DEVICES=1`). Command line invokes vLLM in pooling mode (`--runner pooling`), pointing to `/mnt/models/vllm/Qwen3-VL-Embedding-8B`. FP8 quantization enabled. No external config file; all state in CLI args.

## Dependencies

### Hard (service cannot start or operate without these)
- `tmtdockp01` host (GPU 1 must be available)
- `/mnt/docker/ai/models` (ZFS mount for model weights)
- `nvidia-container-runtime` (GPU passthrough)

### Soft (degrade if these are down, but service still functional)
- `litellm` (routing layer; service remains up but unreachable by UI)

### Reverse (services that depend on THIS service)
- `openwebui` — RAG embedding ingestion and search
- `litellm` — Routes requests to `embed` model name

## State & persistence

- **Database tables / schemas:** None
- **Filesystem state:** `/mnt/docker/ai/cache/huggingface` (RW). Stores downloaded weights and tokenizers. Grows slowly on model refresh.
- **In-memory state:** KV cache (ephemeral). Lost on restart.
- **External state (S3, etc.):** None (ZFS local storage)

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (GPU offloaded) | ? | ? |
| Memory | Host RAM low | ? | ? |
| Disk I/O | Low (mostly read) | ? | ? |
| Network | Low (embedding vectors) | ? | ? |
| GPU (VRAM) | ~14.4GB (0.45 util) | > 15GB (OOM risk) | Shared with `vllm-rerank` on GPU 1 |
| Request latency p50 / p95 / p99 | ? | ? | ? |
| Request rate | ? | ? | ? |

## Failure modes

- **Symptom:** OOM kill or vLLM crash loop.
  - **Root cause:** v0.19.1 memory regression (29GB usage > 32GB limit when combined with rerank).
  - **Mitigation:** Force rollback to `v0.18.1` image tag.
  - **Prevention:** Pin image tag; monitor `vllm-embed` + `vllm-rerank` combined VRAM.

- **Symptom:** High latency on RAG search.
  - **Root cause:** GPU 1 contention with `vllm-rerank` (shared 32GB card).
  - **Mitigation:** Throttle RAG batch size in `openwebui`.
  - **Prevention:** Isolate embed/rerank to separate GPUs if hardware allows.

- **Symptom:** Model not found.
  - **Root cause:**