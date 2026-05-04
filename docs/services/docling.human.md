

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `3` (single-instance stateful) |
| **Tolerable outage** | Hours (RAG ingestion batch window) |
| **Blast radius if down** | RAG ingestion pipeline stalls. `audio-studio` unaffected (uses ASR/TTS only). |
| **Recovery time today** | Auto-restart (`unless-stopped`); manual intervention if GPU lockup occurs. |
| **Owner** | Homelab AI Team (SRE rotation) |

## What this service actually does

Docling performs document extraction (PDF, DOCX, PPTX) into structured text for RAG ingestion. It is GPU-accelerated for OCR and Vision-Language Model (VLM) parsing.

The fleet uses this service primarily as a backend for batch processing documents before embedding. Other services submit files via HTTP POST to `http://tmtdockp03:9400`. It is NOT used for real-time user-facing chat interactions; latency tolerance is higher than ASR/TTS.

Common confusion: This service does not host the vector database. It produces the text payload that is later indexed elsewhere.

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp03-audio/docker-compose.yml` |
| **Image** | `quay.io/docling-project/docling-serve-cu128:v1.15.0` |
| **Pinning policy** | Tag-floating (`v1.15.0`). Not digest pinned. |
| **Resource caps** | GPU 0 (A5000, 24GB) reserved. No CPU/RAM limits defined in `deploy`. |
| **Volumes** | **None defined.** (See State & persistence risk). |
| **Networks** | Default bridge. Port 9400 exposed to host. |
| **Secrets** | `HF_TOKEN` absent from env block (unlike ASR/TTS). |
| **Healthcheck** | `curl -sf http://127.0.0.1:5001/health` (interval 30s, start_period 60s). |

### Configuration shape

Environment variables define host binding and device selection. No external config files loaded. Models are pulled from HuggingFace on first run if missing.

- `DOCLING_SERVE_HOST`: `0.0.0.0`
- `DOCLING_SERVE_PORT`: `5001` (internal)
- `NVIDIA_VISIBLE_DEVICES`: `0`

## Dependencies

### Hard (service cannot start or operate without these)
- **GPU 0 (A5000)** — Container requests `device_ids: ['0']`. Fails to start if GPU is busy or passed to another container.
- **Outbound Internet** — Required to download models from HuggingFace on first start.

### Soft (degrade if these are down, but service still functional)
- **None** — Once models are cached, offline operation is possible (if configured).

### Reverse (services that depend on THIS service)
- **RAG Ingestion Pipeline** — External client sends documents here. Fails if port 9400 is unreachable.
- **`audio-studio`** — Does NOT depend on this service (depends on ASR/TTS only).

## State & persistence

**CRITICAL RISK:** The `docling` service block defines **no volume mounts**, despite comments in the Compose file stating "Models download... persist in Docker volumes."

- **Database tables / schemas:** None.
- **Filesystem state:** HuggingFace cache stored in container writable layer (ephemeral).
    - **Growth rate:** Models are ~1-2GB each.
    - **Risk:** Container restart or image update wipes model cache, forcing re-download and increasing cold-start latency.
    - **Recommendation:** Mount `hf_cache` volume to `/app/models` or `$HOME/.cache/huggingface`.
- **In-memory state:** Model weights loaded into VRAM (~1GB VRAM usage per comment). Lost on container stop.
- **External state:** None.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | 10-20% (idle) | >80% sustained | Throttles if CPU bound (OCR) |
| Memory | 1GB RAM | >4GB | OOM killed if host swaps |
| Disk I/O | Bursty (model load) | >500MB/s | High latency on model pull |
| Network | Low (keepalive) | >50MB/s (upload) | Requests queue |
| GPU (if applicable) | ~1GB VRAM | >12GB (total pool) | Evicts other workloads on GPU 0 |
| Request latency p50 / p95 / p99 | ? | >30s | Timeout on large PDFs |
| Request rate | Low (batch) | >1 concurrent | Serializes processing |

## Failure modes

- **Symptom**: Healthcheck fails, container restarts loop.
    - **Root cause**: GPU memory contention. ASR (~4GB) + TTS (~12GB) + Docling (~1GB) = ~17GB. Burst traffic may spike usage beyond 24GB limit.
    - **Mitigation**: Kill TTS temporarily to free VRAM.
    - **Prevention**: Enforce strict memory limits in `deploy.resources`.

- **Symptom**: "Model not found" errors after update.
    - **Root cause**: Container wipe removes cached models; new image lacks them.
    - **Mitigation**: Manual pull or wait for re-download.
    - **Prevention**: Mount persistent volume for HF cache.

- **Symptom**: Port 9400 in use.
    - **Root cause**: Stale process on host or previous container didn't release port.
    - **Mitigation**: `docker rm -f docling`.
    - **Prevention**: Ensure `restart: unless-stopped` and no external port conflicts.

## HA constraints (input to fleet-reliability design)

- **Replicable?** No. Single GPU 0 binding prevents horizontal scaling on this host.
- **Coordination requirements**: None. Stateless API endpoint (mostly).
- **State sharing across replicas**: N/A. Model cache is local to container currently. If replicated, requires shared FS or separate model download per replica.
- **Hardware bindings**: **Strict.** `NVIDIA_VISIBLE_DEVICES=0`. Cannot migrate to host without A5000 GPU or free GPU 0.
- **Network constraints**: Port 9400 must be unique. No multicast/broadcast required.
- **Cluster size constraints**: Single instance only. Cannot run on dockp02 (ACE-Step relocated there, GPU 1).
- **Migration cost**: High.