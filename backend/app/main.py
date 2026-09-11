from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .database.database import Base, engine, PROJECT_ROOT, ensure_compatibility_columns, reset_runtime_statuses
from .database import models
from .api.cameras import router as cameras_router
from .api.alerts import router as alerts_router
from .api.events import router as events_router
from .api.detections import router as detections_router
from .api.analytics import router as analytics_router
from .api.streams import router as streams_router
from .api.websocket import router as websocket_router
from .api.zones import router as zones_router
from .api.auth import router as auth_router
from .api.settings import router as settings_router
from .core.security import get_current_operator, get_stream_operator


load_dotenv()


app = FastAPI(
    title="Sentinel AI Border Control Unit",
    version="0.1.0",
    description=(
        "AI-powered intelligent border surveillance "
        "and video analytics platform."
    ),
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

Base.metadata.create_all(bind=engine)
ensure_compatibility_columns()
reset_runtime_statuses()
EVIDENCE_DIR = PROJECT_ROOT / "data" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# API Routers
# ---------------------------------------------------------

app.include_router(cameras_router, dependencies=[Depends(get_current_operator)])
app.include_router(auth_router, prefix="/api")
app.include_router(cameras_router, prefix="/api", dependencies=[Depends(get_current_operator)])
app.include_router(alerts_router, prefix="/api", dependencies=[Depends(get_current_operator)])
app.include_router(events_router, prefix="/api", dependencies=[Depends(get_current_operator)])
app.include_router(detections_router, prefix="/api", dependencies=[Depends(get_current_operator)])
app.include_router(analytics_router, prefix="/api", dependencies=[Depends(get_current_operator)])
app.include_router(streams_router, prefix="/api", dependencies=[Depends(get_stream_operator)])
app.include_router(websocket_router)
app.include_router(zones_router, dependencies=[Depends(get_current_operator)])
app.include_router(settings_router, prefix="/api")
app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")


# ---------------------------------------------------------
# Root
# ---------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "Sentinel AI Border Control Unit backend is running",
        "version": "0.1.0",
    }


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Sentinel AI Border Control Unit",
        "version": "0.1.0",
    }
