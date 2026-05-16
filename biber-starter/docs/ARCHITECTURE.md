# BIBER Architecture

Recommended services:

```text
React Admin UI
    |
FastAPI API Gateway
    |
Auth + Passcode Service
    |
GPU Scheduler
    |
Redis Queue  ---- MySQL
    |
GPU Workers
    |
Models: biber-dev-core, biber-video-core, biber-audio-core, biber-proctor-core
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
