from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .database.database import Base, engine, ensure_compatibility_columns
from .database import models
from .api.cameras import router as cameras_router
from .api.alerts import router as alerts_router
from .api.events import router as events_router
from .api.detections import router as detections_router
from .api.analytics import router as analytics_router
from .api.streams import router as streams_router
from .api.websocket import router as websocket_router


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
Path("data/evidence").mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# API Routers
# ---------------------------------------------------------

app.include_router(cameras_router)
app.include_router(cameras_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(detections_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(streams_router, prefix="/api")
app.include_router(websocket_router)
app.mount("/evidence", StaticFiles(directory="data/evidence"), name="evidence")


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
