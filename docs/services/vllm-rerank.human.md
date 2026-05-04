

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for replication) |
| **Tolerable outage** | "unplanned outage acceptable for ≤ 1 hour — RAG search degrades but chat continues" |
| **Blast radius if down** | "Open WebUI RAG reranking fails → search results unranked; LiteLLM /v1/rerank returns 503; no chat impact" |
| **Recovery time today** | manual (docker-compose restart on tmtdockp01, requires GPU 1 availability) |
| **Owner** | homelab-ai team (claude-code agent) |

## What this service actually does

vllm-rerank implements the re-ranking stage of the RAG pipeline. When Open WebUI performs document search, it retrieves candidate documents via vector similarity, then sends them through this service to score and reorder results by relevance. The model is Qwen3-VL-Reranker-8B in FP8 quantization.

Other fleet services use it via HTTP API through LiteLLM's `/v1/rerank` endpoint. Open WebUI is the primary consumer, configured with `RAG_RERANKING_MODEL_URL=http://litellm:4000/v1/rerank` and `RAG_TOP_K_RERANKER=3`. LiteLLM acts as the proxy, handling authentication and routing.

This service is NOT used for embeddings (that's vllm-embed on the same GPU), chat completions (vllm-chat), or document extraction (Docling on dockp03). It only scores already-retrieved documents.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.18.1-cu130` |
| **Pinning policy** | tag-pinned v0.18.1 (rollback from v0.19.1 due to pooling model bug + memory regression) |
| **Resource caps** | GPU 1 (RTX PRO 4500, 32GB), `--gpu-memory-utilization 0.40` = 12.8GB cap |
| **Volumes** | `/mnt/docker/ai/models:/mnt/models:ro` (model weights, stateless), `/mnt/docker/ai/cache/huggingface:/root/.cache/huggingface` (downloaded weights, cache) |
| **Networks** | `ai-inference` (internal), accessed via `litellm:4000/v1/rerank` |
| **Secrets** | None (no auth required, internal network only) |
| **Healthcheck** | `curl -f http://127.0.0.1:8002/health`, interval 30s, timeout 10s, retries 3, start_period 120s |

### Configuration shape

Pure command-line configuration via `command` array. Key parameters: `--model /mnt/models/vllm/Qwen3-VL-Reranker-8B`, `--quantization fp8`, `--runner pooling`, `--served-model-name rerank`, `--port 8002`, `--max-model-len 2048`. HF model revision pinned to `b212dc8c91a8164aef1ea2de9c1a867611e75c04` (see model download notes in compose comments).

## Dependencies

### Hard (service cannot start or operate without these)
- None recorded in CMDB. Container will start without other services, but cannot serve requests until network is available.

### Soft (degrade if these are down, but service still functional)
- None. The service is stateless once model is loaded.

### Reverse (services that depend on THIS service)
- **litellm** — routes `/v1/rerank` requests here; RAG pipeline breaks if down
- **openwebui** — uses RAG reranking for search quality; degraded search results if down

## State & persistence

Model weights are stored in `/mnt/docker/ai/models/vllm/Qwen3-VL-Reranker-8B` on local ZFS (NOT NFS, per stack design). Weights are read-only mounted; no writes occur during normal operation. The huggingface cache at `/mnt/docker/ai/cache/huggingface` contains downloaded weights, tokenizer data, and temporary KV cache. This cache can be cleared without data loss but requires re-download on next start.

- **Database tables / schemas**: none
- **Filesystem state**: `/mnt/docker/ai/models/vllm/Qwen3-VL-Reranker-8B` (read-only weights, ~4-8GB), `/mnt/docker/ai/cache/huggingface` (cache, grows with use)
- **In-memory state**: model weights loaded into GPU VRAM (~12.8GB at 0.40 utilization), KV cache for concurrent requests
- **External state**: none

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 5-15% | >70% sustained | throttles request processing |
| Memory | 12.8GB GPU (0.40 utilization) | >90% GPU memory | OOM kill or request queue timeout |
| Disk I/O | minimal (model loaded once) | N/A | N/A |
| Network | <10 Mbps (internal only) | >50 Mbps | connection queue fills |
| GPU | GPU 1, ~40% utilization | >85% total with vllm-embed | contention causes evictions |
| Request latency p50 / p95 / p99 | ~50ms / ~150ms / ~500ms | p99 > 2s | queue builds, latency degrades |
| Request rate | ~10-50 RPS typical | >100 RPS | saturation, dropped requests |

## Failure modes

**Symptom**: Container fails to start with "CUDA out of memory" or healthcheck timeouts  
**Root cause**: GPU 1 contention with vllm-embed (combined utilization 0.85 on 32GB GPU)  
**Mitigation**: Reduce `--gpu-memory-utilization` for either service, or restart vllm-embed to free memory  
**Prevention**: Set combined utilization cap to 0.75-0.80 to maintain headroom for concurrent requests

**Symptom**: Memory regression after vLLM upgrade (container uses 29GB at 0.55 utilization)  
**Root cause**: vLLM v0.19.1 pooling model bug  
**Mitigation**: Rollback to v0.18.1 image (current state)  
**Prevention**: Pin image tag; test pooling runners in staging before upgrade

**Symptom**: LiteLLM returns 503 on `/v1/rerank` calls  
**Root cause**: vllm-rerank healthcheck failed or container crashed  
**Mitigation**: Check container logs (`docker logs vllm-rerank`), restart if stuck  
**Prevention**: Monitor healthcheck status; alert on consecutive failures

## HA constraints (input to fleet-reliability design)

- **Replicable?**: no — single GPU binding, no state replication mechanism
- **Coordination requirements**: none — single instance, no leader election
- **State sharing across replicas**: N/A — no replicas exist; weights shared via read-only ZFS mount
- **Hardware bindings**: GPU 1 (PCI bus AF:00.0, RTX PRO 4500 Blackwell, 32GB) — cannot move to GPU 0 or 2 without reconfiguring vllm-chat EP layout
- **Network constraints**: port 8002 must be unique; internal ai-inference network only (not exposed externally)
- **Cluster size constraints**: N/A — single-instance only
- **Migration cost**: high — requires GPU reassignment, model reload, and potential reconfiguration of vllm-embed (shares GPU 1)

**Critical constraint**: vllm-rerank and vllm-embed share GPU 1. Combined `--gpu-memory-utilization` is 0.85 (0.40 + 0.45). This leaves ~4.8GB headroom on 32GB GPU. Any increase in either service's utilization cap risks OOM. Fleet redesign must either:
1. Assign dedicated GPU to reranking (requires additional hardware or moving vllm-chat shard)
2. Reduce combined utilization to 0.75-0.80 with explicit headroom monitoring
3. Consolidate embed+rerank into single container with separate runner threads (untested)

## Operational history

### Recent incidents (last 90 days)
- 2026-04-12 — vLLM v0.19.1 upgrade caused memory regression (29GB at 0.55 utilization); rollback to v0.18.1 within 2 hours. See compose comments for details.
- 2026-04-16 — Model refresh: Qwen/Qwen