from pathlib import Path
import re
import shutil
import uuid

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.database import PROJECT_ROOT, get_db
from ..database.models import Camera
from ..database.schemas import CameraCreate, CameraResponse, CameraUpdate, RtspTestRequest
from ..services.camera_service import (
    create_camera,
    delete_camera,
    get_camera,
    get_cameras,
    update_camera,
)
from ..video.stream_manager import StreamManager


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)

VIDEO_DIR = PROJECT_ROOT / "data" / "videos"


@router.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Store and validate an uploaded MP4 as a project-relative camera source."""
    filename = Path(file.filename or "")
    if filename.suffix.lower() != ".mp4":
        raise HTTPException(status_code=415, detail="Only .mp4 video files are supported")

    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", filename.stem).strip("._") or "camera_video"
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    target = VIDEO_DIR / f"{safe_stem}.mp4"
    if target.exists():
        target = VIDEO_DIR / f"{safe_stem}_{uuid.uuid4().hex[:8]}.mp4"

    try:
        with target.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        if target.stat().st_size == 0:
            raise ValueError("The uploaded video is empty")

        capture = cv2.VideoCapture(str(target))
        valid = capture.isOpened() and capture.get(cv2.CAP_PROP_FRAME_COUNT) > 0
        capture.release()
        if not valid:
            raise ValueError("OpenCV could not open the uploaded MP4")
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Unable to store the uploaded video") from exc
    finally:
        await file.close()

    return {"filename": target.name, "stream_url": f"data/videos/{target.name}", "source_type": "video"}


@router.get(
    "",
    response_model=list[CameraResponse],
)
def list_cameras(
    db: Session = Depends(get_db),
):
    return get_cameras(db)


@router.post("/test-rtsp")
def test_rtsp_connection(request: RtspTestRequest):
    try:
        reachable = StreamManager.test_connection(request.stream_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "reachable": reachable,
        "status": "online" if reachable else "offline",
        "message": "RTSP stream is reachable." if reachable else "Unable to connect to RTSP camera.",
    }


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
)
def read_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    camera = get_camera(db, camera_id)

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return camera


@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_camera(
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Camera)
        .filter(Camera.camera_code == camera_data.camera_code)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Camera code already exists",
        )

    return create_camera(db, camera_data)


@router.delete(
    "/{camera_id}",
)
def remove_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    deleted = delete_camera(db, camera_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return {
        "message": "Camera deleted successfully",
        "camera_id": camera_id,
    }


@router.put("/{camera_id}", response_model=CameraResponse)
def edit_camera(camera_id: int, camera_data: CameraUpdate, db: Session = Depends(get_db)):
    try:
        camera = update_camera(db, camera_id, camera_data.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Camera code already exists") from exc
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera
