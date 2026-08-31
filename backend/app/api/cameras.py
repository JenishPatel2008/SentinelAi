from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Camera
from ..database.schemas import CameraCreate, CameraResponse
from ..services.camera_service import (
    create_camera,
    delete_camera,
    get_camera,
    get_cameras,
)


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


@router.get(
    "",
    response_model=list[CameraResponse],
)
def list_cameras(
    db: Session = Depends(get_db),
):
    return get_cameras(db)


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