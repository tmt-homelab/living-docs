

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope for standard HA) |
| **Tolerable outage** | Unplanned outage acceptable for ≤ 4 hours (non-critical) |
| **Blast radius if down** | `audio-studio` TTS tab fails; `/v1/audio/speech` endpoint returns 503 |
| **Recovery time today** | Auto-restart (`unless-stopped`); model reload takes ~300s on cold boot |
| **Owner** | `claude-code` (automated registration); Homelab AI Team (operational) |

## What this service actually does

Performs Text-to-Speech (TTS) inference using the Qwen3-TTS model. It exposes an OpenAI-compatible API at `/v1/audio/speech` on host port 9200. The fleet uses it primarily as a backend for the `audio-studio` web interface and any internal automation requiring voice synthesis.

It is NOT used for Speech-to-Text (ASR)—that is handled by `qwen3-asr` on the same host. It is NOT a general-purpose audio mixer or stream processor.

The service downloads models from HuggingFace on first start and caches them in Docker volumes. It requires a valid `HF_TOKEN` for gated models. If the model fails to load, the container stays healthy but returns errors on inference requests.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp03-audio/docker-compose.yml` |
| **Image** | Build from context `https://github.com/groxaxo/Qwen3-TTS-Openai-Fastapi.git#main` |
| **Pinning policy** | Branch `main` (floating); risk of upstream breakage on push |
| **Resource caps** | GPU 0 reserved (A5000 24GB); No explicit CPU/RAM limits |
| **Volumes** | `qwen3_tts_models` (state: model weights), `qwen3_tts_voice_library` (state: voices) |
| **Networks** | Default bridge; Host port 9200 bound |
| **Secrets** | `HF_TOKEN` (injected via env; managed by 1Password/CI/CD) |
| **Healthcheck** | `curl http://127.0.0.1:8880/health` (every 30s, 5m start period) |

### Configuration shape

Configuration is purely environment-driven. No external config files.
- `TTS_MODEL_NAME`: Sets the HF model ID (default `Qwen/Qwen3-TTS-12Hz-1.7B-Base`).
- `HF_HOME`: Points to the mounted model volume.
- `NVIDIA_VISIBLE_DEVICES`: Hardcoded to `0`.
- `TTS_WARMUP_ON_START`: True (blocks startup until model loaded).

## Dependencies

### Hard (service cannot start or operate without these)
- **NVIDIA GPU 0** — Required for inference. Shared with `qwen3-asr` and `docling`.
- **HuggingFace Token** — Required if model is gated; otherwise model download fails.
- **Internet** — Required for initial model download (not for subsequent runs if cached).

### Soft (degrade if these are down, but service still functional)
- **None** — Once models are cached, no external deps for inference.

### Reverse (services that depend on THIS service)
- **`audio-studio`** — UI calls port 9200. Breaks TTS tab completely.
- **External Clients** — Any service calling `http://tmtdockp03:9200/v1/audio/speech`.

## State & persistence

- **Database tables / schemas**: None.
- **Filesystem state**:
    - `/app/models` (Volume `qwen3_tts_models`): ~10-15GB persistent model weights. Grows with new model versions.
    - `/app/voice_library` (Volume `qwen3_tts_voice_library`): User-generated voice presets.
- **In-memory state**: GPU VRAM cache (~12GB). Lost on restart.
- **External state**: HuggingFace Hub (download source).

**HA Implication**: State is local to `tmtdockp03`. Cannot migrate state to another node without copying volumes and ensuring GPU compatibility.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | Low (<10%) | >80% sustained | N/A |
| Memory | ? (Container limits) | >90% usage | OOM Kill |
| Disk I/O | High on start (model load) | ? | N/A |
| Network | ? (Audio stream) | >100Mbps | ? |
| GPU (if applicable) | ~12GB VRAM used | >20GB total (Host) | OOM on GPU |
| Request latency p50 | ? | >5s | Timeout |
| Request rate | ? | >10 req/s | Queueing/Drop |

## Failure modes

- **GPU Memory Contention**: `qwen3-asr` (~4GB), `qwen3-tts` (~12GB), `docling` (~1GB) share GPU 0 (24GB). Burst load from `qwen3-asr` can OOM `qwen3-tts`.
    - **Symptom**: Container restarts or inference hangs.
    - **Mitigation**: Kill `docling` or `qwen3-asr` temporarily to free VRAM.
- **Model Cache Corruption**: Disk write failure during model download.
    - **Symptom**: 500 errors on inference; healthcheck passes.
    - **Mitigation**: `docker volume rm qwen3_tts_models` and restart.
- **HF_TOKEN Expiry**: Token revoked or expired.
    - **Symptom**: Model update fails; container stays up but cannot load new models.
    - **Mitigation**: Rotate `HF_TOKEN` in 1Password/Env.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Tightly bound to specific GPU architecture (NVIDIA A5000).
- **Coordination requirements**: None.
- **State sharing across replicas**: None. State is local volume-bound.
- **Hardware bindings**:
    - **GPU**: Must run on `tmtdockp03` GPU 0.
    - **Driver**: Requires specific CUDA version matching image build.
    - **PCIe**: Shares PCIe bus with `qwen3-asr` and `docling` (potential bandwidth contention).
- **Network constraints**: Host port 9200 must be unique. Internal port 8880 used for healthcheck.
- **Cluster size constraints**: Single instance only. Cannot scale horizontally due to GPU binding.
- **Migration cost**: High. Moving requires:
    1.  Identifying another node with NVIDIA GPU + CUDA compatibility.
    2.  Copying `qwen3_tts_models` volume (~15GB).
    3.  Updating host port mapping.
    4.  Updating DNS/Proxy routing for port 9200.
- **VRAM Budget**: Strict limit of 24GB total on host. `qwen3-tts` consumes ~50% of host VRAM alone. Any other GPU workload on GPU 0 risks instability.

## Operational history

### Recent incidents (last 