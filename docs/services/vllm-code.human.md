

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope) |
| **Tolerable outage** | "Unplanned outage acceptable for ≤ 1 hour" (Non-critical per CMDB) |
| **Blast radius if down** | LiteLLM `code` group fails → Code assistants degrade to `chat` fallback or 502s. |
| **Recovery time today** | Manual (docker restart / rollback digest) |
| **Owner** | AI Infra Team (registered by `phase-1.4-bulk-backfill`) |

## What this service actually does

Hosts the MiniMax M2.7 NVFP4 (230B MoE) inference endpoint for code generation tasks. Consumed by LiteLLM gateway via OpenAI-compatible API. Handles tool-calling (`minimax_m2` parser) and reasoning (`minimax_m2_append_think`).

The fleet uses it specifically for the `code` role in LiteLLM routing. When down, users lose structured tool output and reasoning capabilities for code tasks; they fall back to the `chat` group (Qwen3.5) which lacks native tool parsing for this model family.

It is NOT used for audio processing (GPU 0 is reserved for `dockp03-audio`) or general chat (handled by other shards). It does not persist conversation history; state is purely in-flight KV cache.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/ai-gpu3/docker-compose.yml` |
| **Image** | `vllm/vllm-openai:v0.20.0-cu130@sha256:77797441eae630c2e79eefa03957b3d61a278670f2a9928d64ce102e7a0790cc` |
| **Pinning policy** | Digest pinned (rollback: `sha256:2ccff44e7b60ed43093004af99b57ae49855c9d49c411c6707807a49a6eb0e8e`) |
| **Resource caps** | GPU 1,2 (RTX PRO 6000 Blackwell Max-Q 98GB). CPU: ? (OMP_NUM_THREADS=4) |
| **Volumes** | `/mnt/docker/ai/models` (RO), `/mnt/docker/ai/models/cache/huggingface` (RW) |
| **Networks** | `ai-gpu3` (bridge) |
| **Secrets** | None (model weights stored on local disk) |
| **Healthcheck** | `curl -f http://127.0.0.1:8000/health` (900s start_period) |

### Configuration shape

CLI arguments passed directly to vLLM entrypoint. Key flags: `--tensor-parallel-size 2`, `--enable-expert-parallel`, `--kv-cache-dtype turboquant_k8v4`. Environment variables control CUDA visibility (`NVIDIA_VISIBLE_DEVICES=1,2`) and library paths. Model config (`config.json`) contains NVFP4 quantization settings; vLLM auto-detects, no `--quantization` flag required.

## Dependencies

### Hard (service cannot start or operate without these)
- **NVIDIA Drivers (Host)** — Required for `runtime: nvidia`. If host drivers mismatch image CUDA version, container fails to start.
- **GPU 1 & 2 Availability** — Physical binding required. Service cannot run on CPU or other GPUs.

### Soft (degrade if these are down, but service still functional)
- **Model Storage (`/mnt/docker/ai/models`)** — If mounted read-only fails, container starts but model load fails.
- **LiteLLM Gateway** — Upstream traffic stops, service remains healthy but idle.

### Reverse (services that depend on THIS service)
- **LiteLLM (`code` group)** — Routes `minimax-m27` requests here. Fails over to `chat` group on 5xx.
- **Internal Dev Tools** — Direct curl testing against port 8000.

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**: `/mnt/docker/ai/models/cache/huggingface` (writable cache, deletable). `/mnt/docker/ai/models` (RO, contains 117GB model weights).
- **In-memory state**: KV cache (TurboQuant k8v4). Lost on restart. `--enable-prefix-caching` requires memory retention across requests.
- **External state**: None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (<10%) | >50% | Not limiting factor |
| Memory | ~58GB/GPU | OOM Killer | vLLM enforces `--gpu-memory-utilization 0.92` |
| Disk I/O | Burst on load | N/A | Model load is disk-bound initially |
| Network | ~100Mbps (ingress) | 1Gbps | Bottlenecked by GPU compute, not NIC |
| GPU (if applicable) | 90% Util (FP4) | 100% / Temp >80C | Throttling on thermal limits |
| Request latency p50 | ~200ms (TTFT) | >2s | Grows linearly with context |
| Request rate | 1-2 req/s (concurrent) | >2 req/s | `--max-num-seqs 2` hard limit |

## Failure modes

- **Symptom**: Container restart loop. **Root cause**: GPU OOM. **Mitigation**: Lower `--gpu-memory-utilization` to 0.85. **Prevention**: Monitor `nvidia-smi` before updates.
- **Symptom**: Spurious spaces in output. **Root cause**: Tokenization regression. **Mitigation**: Revert image to `nvidia` official tag (see compose comments re: `lukealonso` issue). **Prevention**: Verify modelopt calibration on new tags.
- **Symptom**: 502 from LiteLLM. **Root cause**: Healthcheck timeout (900s start period too short for cold boot?). **Mitigation**: Increase start_period. **Prevention**: Keep model loaded via warm-up script.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No (Single-instance stateful due to hardware binding).
- **Coordination requirements**: None (Standalone).
- **State sharing across replicas**: N/A (No replicas).
- **Hardware bindings**: **Strict.** Requires NVIDIA RTX PRO 6000 Blackwell Max-Q (GPU 1 & 2) on host `tmtdockp03` (192.168.20.17). Cannot migrate to host with different GPU architecture (e.g., Ampere) without model re-quantization.
- **Network constraints**: Port 8000 must be unique per host. Internal bridge `ai