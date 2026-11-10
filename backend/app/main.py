
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import Base, engine
from app import models
from app.routes.reminders import router as reminders_router
from app.routes.auth import router as auth_router
from app.routes.links import router as links_router
from app.routes.scheduler import router as scheduler_router
from app.services.gnani_service import GnaniService
from app.routes.health import router as health_router
from app.routes.users import router as users_router
from app.services.reminder_scheduler import start_scheduler, stop_scheduler


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env.lower() == "development" and engine is not None:
        try:
            await run_in_threadpool(Base.metadata.create_all, bind=engine)
        except Exception as exc:
            logger.warning(
                "Development table creation failed (%s)", type(exc).__name__
            )
    start_scheduler(gnani)
    try:
        yield
    finally:
        stop_scheduler()


# Initialize FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered family voice assistance and medicine reminder system",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gnani services
gnani = GnaniService()


# TTS request model
class GenerateAudioRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    voice: str | None = None
    language: str = "te-IN"


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to Apno Ki Awaaz",
        "environment": settings.app_env,
    }


# Health endpoint
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(links_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(reminders_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")


# Gnani Text-to-Speech endpoint
@app.post("/api/voice/generate")
async def generate_audio(request: GenerateAudioRequest):
    try:
        audio = gnani.generate_speech(
            text=request.text,
            voice=request.voice,
            language=request.language,
        )

        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'attachment; filename="reminder.wav"'
            },
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Gnani TTS request failed",
        ) from None


# Gnani Speech-to-Text endpoint
@app.post("/api/voice/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Audio filename is required",
        )

    allowed_extensions = {".wav", ".mp3", ".ogg", ".webm"}
    extension = Path(file.filename).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio file format",
        )

    temp_path = Path("uploads") / f"{uuid4().hex}{extension}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded audio file is empty",
            )

        temp_path.write_bytes(content)

        transcript = gnani.transcribe_audio(
            str(temp_path),
            language="te-IN",
        )

        return {
            "transcript": transcript,
            "language": "te-IN",
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Gnani STT request failed",
        ) from None

    finally:
        temp_path.unlink(missing_ok=True)
