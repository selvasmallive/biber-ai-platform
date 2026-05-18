# BIBER Architecture

Recommended services:

```text
React Admin UI
    |
FastAPI API Gateway
    |
Auth + Passcode Service
    |
Optional OpenAI Mentor Service
    |
GPU Scheduler
    |
Redis Queue  ---- MySQL
    |
GPU Workers / vLLM OpenAI-Compatible Runtime
    |
Models: biber-dev-core, biber-video-core, biber-audio-core, biber-proctor-core
```

Phase 1 immediate chat path:

```text
Developer
 -> /v1/chat
 -> optional mentor notes
 -> biber-dev-core vLLM service
 -> response
 -> optional GitHub save
 -> optional Azure Blob backup
```

XRIQ private-devnet client path:

```text
Developer or BIBER client
 -> /v1/xriq/private-devnet/status
 -> /v1/xriq/private-devnet/accounts/{address}
 -> /v1/xriq/private-devnet/transactions/{hash}
 -> /v1/xriq/private-devnet/preflight-transfer
 -> server-side BIBER XRIQ wrapper
 -> xriq-node ... --format json
 -> file-backed private-devnet chain and pending state
 -> stable JSON response
```

Video/proctoring path:

```text
Upload media
 -> Store file
 -> Extract metadata with ffprobe
 -> Extract frames/audio with ffmpeg
 -> Run CV/audio models
 -> Generate events
 -> Human review timeline
```
