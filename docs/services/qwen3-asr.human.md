

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `4` (hardware-bound, out of scope) |
| **Tolerable outage** | "Unplanned outage acceptable for ≤ 4 hours" (Homelab inference) |
| **Blast radius if down** | `audio-studio` UI transcription disabled. RAG audio ingestion pipeline stalls. |
| **Recovery time today** | Auto-restart (`unless-stopped`). Manual GPU reset if hang occurs. |
| **Owner** | `claude-code` (agent), `tmt-homelab` (org) |

## What this service actually does

Performs Speech-to-Text (ASR) inference via OpenAI-compatible API (`/v1/audio/transcriptions`). Hosts `Qwen/Qwen3-ASR-1.7B` model on GPU 0.

Consumed by `audio-studio` (Streamlit UI) for user voice input processing. Also used potentially by RAG pipelines for converting audio recordings to text before vector embedding.

It is NOT used for Text-to-Speech (handled by `qwen3-tts`) or document extraction (handled by `docling`). It does not store conversation history or user data persistently beyond model weights.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp03-audio/docker-compose.yml` |
| **Image** | Built from `https://github.com/Si-ris-B/Qwen3-ASR-FastAPI-Docker.git#fastapi-prod` |
| **Pinning policy** | Tag-floating (git branch `fastapi-prod`). No SHA digest. |
| **Resource caps** | GPU 0 (NVIDIA A5000 24GB). No CPU/Mem hard limits defined in compose. |
| **Volumes** | `qwen3_asr_models` (stateful model cache at `/app/models`). |
| **Networks** | Default bridge. Exposed `9100` on host `tmtdockp03`. |
| **Secrets** | `HF_TOKEN` (injected via env from 1Password Connect). |
| **Healthcheck** | `GET http://127.0.0.1:8000/health` (Python urllib, 30s interval, 5m start_period). |

### Configuration shape

Environment variables drive runtime behavior. `DEFAULT_MODEL` sets the HF repo ID. `DEFAULT_DEVICE=cuda:0` forces GPU usage. `HF_HOME` redirects model cache to volume. No external config files; all config via env.

## Dependencies

### Hard (service cannot start or operate without these)
- **NVIDIA GPU 0** — `tmtdockp03` device `0`. Without this, container crashes or hangs (no CPU fallback).
- **HuggingFace Token** — Required if model is gated (comment indicates `HF_TOKEN` set via CI/CD).
- **Internet Access** — Required on first start to download `Qwen/Qwen3-ASR-1.7B` weights.

### Soft (degrade if these are down, but service still functional)
- **None** — Once models are cached, external network not required for inference.

### Reverse (services that depend on THIS service)
- **`audio-studio`** — UI calls ASR endpoint for transcription. Breaks transcription feature immediately if down.

## State & persistence

State is primarily the model weights cached locally. This is critical for boot time (avoiding 10GB+ download).

- **Database tables / schemas**: None.
- **Filesystem state**: `/app/models` (Volume `qwen3_asr_models`). Contains PyTorch/HF checkpoints. Growth rate ~4GB per model version.
- **In-memory state**: Inference context (audio buffers). Lost on restart.
- **External state**: None.

**Backup Strategy:** Volume `qwen3_asr_models` must be included in host-level backup. Re-downloading models is slow and rate-limited by HF.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | < 10% (GPU bound) | > 80% sustained | N/A |
| Memory | ~4GB VRAM | > 20GB VRAM | OOM Kill if TTS/Docling spike |
| Disk I/O | Low (read-heavy) | High write during start | Model load latency |
| Network | Low (API requests) | High bandwidth | Queue buildup |
| GPU (if applicable) | Spiky (inference) | 100% for > 5m | Throttling |
| Request latency p50 | ~2s | > 10s | Timeout |
| Request rate | < 10 req/min | > 50 req/min | Queue depth > 10 |

## Failure modes

- **Symptom**: `audio-studio` transcription returns 500 error.
  - **Root cause**: GPU OOM. `qwen3-tts` and `docling` share GPU 0. Total VRAM budget (~17GB) is tight on 24GB card; burst load causes eviction.
  - **Mitigation**: Restart `qwen3-asr` to clear VRAM. Monitor `nvidia-smi`.
  - **Prevention**: Enforce strict concurrency limits in `qwen3-tts` to protect ASR headroom.

- **Symptom**: Service starts but hangs on `/health`.
  - **Root cause**: Model download stuck behind HF rate limits or token auth failure.
  - **Mitigation**: Check `HF_TOKEN` validity. Inspect container logs for HTTP 401/429.
  - **Prevention**: Cache volume backup ensures warm start.

- **Symptom**: `NVIDIA_VISIBLE_DEVICES=0` not found.
  - **Root cause**: Host GPU driver mismatch or container runtime failure.
  - **Mitigation**: Reboot `tmtdockp03` if driver stuck.
  - **Prevention**: Monitor host GPU health alerts.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Single GPU 0 binding prevents active-active on same host.
- **Coordination requirements** None. Stateless API layer over local model.
- **State sharing across replicas** None. Model cache is local to volume.
- **Hardware bindings** **CRITICAL**: Requires `tmtdockp03` GPU 0 (A5000). Cannot migrate to `dockp02` (RTX PRO 6000) or CPU-only nodes without code changes.
- **Network constraints** Port `9100` must be unique. Internal `8000` used for healthcheck.
- **Cluster size constraints** Single instance only.
- **Migration cost** High. Requires identical GPU hardware or model quantization adaptation.
- **Resource contention** Shares GPU 0 with `qwen3-tts` and `docling`.