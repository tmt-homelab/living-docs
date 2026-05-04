

# Expert Brief

## Class & posture

| Field | Value |
|-------|-------|
| **Fleet-reliability class** | `1` (stateless) — but depends on class `3` backends |
| **Tolerable outage** | hours — non-critical, user-facing only |
| **Blast radius if down** | Users lose unified audio UI; ASR/TTS APIs remain accessible directly |
| **Recovery time today** | auto-restart (unless-stopped) — 60s start period |
| **Owner** | tmt-homelab team — agent ID: homelab-ai/phase-1.4 |

## What this service actually does

Streamlit web UI that exposes ASR (speech-to-text), TTS (text-to-speech), and music generation (via remote ace-step) as a unified interface. The fleet uses it as a consumer-facing entry point for audio workflows. When it's broken, users can still hit ASR/TTS APIs directly at ports 9100/9200.

This service is NOT used for:
- Direct inference (no GPU allocation)
- Model hosting (models live in qwen3-asr/qwen3-tts containers)
- Document processing (docling runs independently on port 9400)

## How it's deployed

| Field | Value |
|-------|-------|
| **Compose path** | `homelab-ai/stacks/dockp03-audio/docker-compose.yml` |
| **Image** | `audio-studio:latest` (local build from `./audio-studio/`) |
| **Pinning policy** | tag-floating (`:latest`) — local development stack |
| **Resource caps** | 1.0 CPU, 2G memory — no GPU reservation |
| **Volumes** | `/tmp/audio-studio:/tmp/audio-studio` (ephemeral), `qwen3_tts_voice_library:/app/voice_library` (shared with qwen3-tts) |
| **Networks** | Default bridge — no external exposure (Caddy proxy handles routing) |
| **Secrets** | None directly consumed (HF_TOKEN used by qwen3-asr/tts, not here) |
| **Healthcheck** | `curl -sf http://localhost:8501/` — 30s interval, 10s timeout, 5 retries, 60s start period |

### Configuration shape

Minimal env surface: only `PYTHONUNBUFFERED=1` set. Backend endpoints hardcoded in Streamlit code:
- `qwen3-asr:8000` for transcription
- `qwen3-tts:8880` for speech synthesis
- `http://192.168.20.16:9300` for ace-step music generation (remote, dockp02)

## Dependencies

### Hard (service cannot start or operate without these)
- `qwen3-asr` — ASR backend; startup blocked until healthy (depends_on condition: service_healthy)
- `qwen3-tts` — TTS backend; startup blocked until healthy (depends_on condition: service_healthy)
- `qwen3_tts_voice_library` volume — shared with qwen3-tts; must exist for voice presets

### Soft (degrade if these are down, but service still functional)
- `ace-step` (192.168.20.16:9300) — music generation feature unavailable if remote service down
- `docling` (port 9400) — document upload features unavailable (separate service, no hard dependency)

### Reverse (services that depend on THIS service)
- None — audio-studio is a terminal consumer (UI layer)

## State & persistence

- **Database tables/schemas**: ?
- **Filesystem state**: `/tmp/audio-studio` — ephemeral uploads/processing; cleared on container restart
- **Shared volume state**: `qwen3_tts_voice_library:/app/voice_library` — contains TTS voice presets; persisted, shared with qwen3-tts
- **In-memory state**: Streamlit session state — lost on restart (standard Streamlit behavior)
- **External state**: None

**Backup strategy**: None — ephemeral by design. Voice library backed up indirectly via qwen3-tts volume.

## Behavior baselines

| Metric | Steady-state | Alert threshold | Saturation behavior |
|--------|--------------|-----------------|--------------------|
| CPU | ~0.2 cores | >0.8 cores sustained | Throttles to 1.0 limit |
| Memory | ~200-500MB | >1.8GB | OOM kill at 2G limit |
| Disk I/O | Minimal (uploads only) | N/A | N/A |
| Network | ~1-5MB/s (user sessions) | N/A | N/A |
| GPU | 0% | N/A | N/A |
| Request latency p50/p95/p99 | ?/ ?/ ? | N/A | N/A |
| Request rate | ~10-50 req/min (idle) | N/A | N/A |

## Failure modes

| Symptom | Root cause | Mitigation | Prevention |
|---------|------------|------------|------------|
| Healthcheck fails (port 8501 unreachable) | Streamlit crash on startup (missing backend) | `docker-compose up -d` restart | Ensure ASR/TTS healthy first |
| Voice presets missing | qwen3_tts_voice_library volume not mounted | Check volume mount, restart | Add volume existence check in CI |
| Music gen unavailable | ace-step at 192.168.20.16:9300 down | UI shows error, no retry | Alert on dockp02 network reachability |
| HF_TOKEN not propagated | CI/CD secret injection failure | Manual env set, restart | Add HF_TOKEN validation in healthcheck |

## HA constraints (input to fleet-reliability design)

- **Replicable?** No — Streamlit stateful sessions per user; multiple instances would break session continuity without Redis/session store
- **Coordination requirements**: None (single-instance only)
- **State sharing across replicas**: N/A — not replicable
- **Hardware bindings**: None (no GPU, no USB)
- **Network constraints**: Port 8501 must be unique per host (currently only one instance)
- **Cluster size constraints**: Single-instance only by design
- **Migration cost**: Low — could move to any host with docker-compose, but backend dependencies (ASR/TTS on dockp03, ace-step on dockp02) create cross-host latency
- **Critical path dependency**: qwen3-asr and qwen3-tts are class-3 (GPU-bound, single-instance) — audio-studio HA would require ASR/TTS HA first

## Operational history

### Recent incidents (last 90 days)
- Unknown — service created 2026-05-01, no recorded incidents in CMDB

### Recurring drift / chronic issues
- None recorded
- Common pattern: HF_TOKEN not set on first run → model download failures (affects qwen3-asr/tts, not audio-studio directly)

### Known sharp edges
- `qwen3_tts_voice_library` volume must exist before audio-studio starts — if qwen3-tts is removed/renamed, audio-studio will fail to mount
- Port 8501 exposed on host — should be proxied via Caddy (comment says "exposed via Caddy reverse proxy only" but ports are bound)

## Open questions for Architect

- Should audio-studio be moved behind Caddy proxy (remove port binding 8501)?
- What is the session persistence strategy for Streamlit? (Currently none — user state lost on restart)
- Should ace-step dependency be made explicit in compose (network/depends_on)?
- Is the `:latest` tag acceptable for production, or should we pin to a digest?
- What is the RPO/RTO requirement for the voice library volume?

## Reference

- **Compose**: `homelab-ai/stacks/dockp03-audio/docker-compose.yml`
- **Logs**: `docker logs audio-studio` (json-file, 10m max-size, 3 files retention)
- **Dashboards**: ?
- **Runbooks**: ?
- **Upstream docs**: Local build (./audio-studio/)
- **Related services**: [`qwen3-asr`](services/qwen3-asr.human.md), [`qwen3-tts`](services/qwen3-tts.human.md), [`docling`](services/docling.human.md), [`ace-step`](services/ace-step.human.md)