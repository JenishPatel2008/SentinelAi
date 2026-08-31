from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .database.database import Base, engine
from .database import models
from .api.cameras import router as cameras_router


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


# ---------------------------------------------------------
# API Routers
# ---------------------------------------------------------

app.include_router(cameras_router)


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