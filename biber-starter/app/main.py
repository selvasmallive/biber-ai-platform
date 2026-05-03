from fastapi import FastAPI, Depends, Header, UploadFile, File
from pydantic import BaseModel
from app.auth import require_api_key, get_priority_from_passcode
from app.config import settings
from app.scheduler import scheduler

app = FastAPI(
    title="BIBER AI Platform",
    version="0.1.0",
    description="Starter API for BIBER private GPU-backed AI platform"
)

class ChatRequest(BaseModel):
    message: str
    model: str | None = None

class CodeRequest(BaseModel):
    prompt: str
    language: str
    model: str | None = None

class VideoRequest(BaseModel):
    prompt: str
    video_path: str | None = None
    model: str | None = "biber-video-core"

class AudioRequest(BaseModel):
    prompt: str
    audio_path: str | None = None
    model: str | None = "biber-audio-core"

class ProctorAnalyzeRequest(BaseModel):
    session_id: str
    prompt: str | None = "Analyze proctoring session"
    model: str | None = "biber-proctor-core"

@app.get("/health")
def health():
    return {"status": "ok", "service": "biber-api"}

@app.get("/v1/models")
def models(auth=Depends(require_api_key)):
    return {
        "models": [
            "biber-dev-core",
            "biber-code-python",
            "biber-code-react",
            "biber-code-dotnet",
            "biber-code-java",
            "biber-code-rust",
            "biber-video-core",
            "biber-audio-core",
            "biber-proctor-core"
        ]
    }

@app.post("/v1/chat")
def chat(req: ChatRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or settings.default_model, "chat", req.model_dump(), priority)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "priority": priority,
        "message": "Job accepted. Worker integration is starter placeholder."
    }

@app.post("/v1/code")
def code(req: CodeRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-dev-core", "code", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/video")
def video(req: VideoRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-video-core", "video", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/audio")
def audio(req: AudioRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-audio-core", "audio", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/proctor/session/analyze")
def proctor_analyze(req: ProctorAnalyzeRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-proctor-core", "proctor", req.model_dump(), priority)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "priority": priority,
        "risk_policy": "AI output is advisory only. Human review required for medium/high risk."
    }

@app.post("/v1/proctor/session/upload")
async def upload_proctor_media(file: UploadFile = File(...), auth=Depends(require_api_key)):
    content = await file.read()
    path = f"/storage/{file.filename}"
    with open(path, "wb") as f:
        f.write(content)
    return {"filename": file.filename, "stored_path": path, "bytes": len(content)}

@app.get("/admin/jobs")
def admin_jobs():
    return {"jobs": [j.__dict__ | {"status": j.status.value, "created_at": j.created_at.isoformat()} for j in scheduler.list_jobs()]}

@app.get("/admin/gpu")
def admin_gpu():
    return {
        "message": "Use nvidia-smi on host for true GPU status. This is API placeholder.",
        "policy": {
            "level_0": "100% GPU",
            "level_1": "20% GPU",
            "level_2": "queue priority",
            "level_3": "standard"
        }
    }
