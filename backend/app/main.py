from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = os.getenv(
    "APP_NAME",
    "Sentinel AI Border Control Unit"
)

APP_VERSION = os.getenv(
    "APP_VERSION",
    "0.1.0"
)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "AI-powered intelligent border surveillance "
        "and video analytics platform."
    ),
)


@app.get("/")
async def root():
    return {
        "message": "Sentinel AI Border Control Unit backend is running",
        "version": APP_VERSION,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION,
    }