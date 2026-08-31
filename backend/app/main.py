from fastapi import FastAPI
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


Base.metadata.create_all(bind=engine)

app.include_router(cameras_router)


@app.get("/")
async def root():
    return {
        "message": "Sentinel AI Border Control Unit backend is running",
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Sentinel AI Border Control Unit",
        "version": "0.1.0",
    }