from sqlalchemy.orm import Session

from ..database.models import Camera
from ..database.schemas import CameraCreate


def get_cameras(db: Session) -> list[Camera]:
    return (
        db.query(Camera)
        .order_by(Camera.id)
        .all()
    )


def get_camera(
    db: Session,
    camera_id: int,
) -> Camera | None:
    return (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )


def create_camera(
    db: Session,
    camera_data: CameraCreate,
) -> Camera:
    camera = Camera(
        camera_code=camera_data.camera_code,
        name=camera_data.name,
        sector=camera_data.sector,
        stream_url=camera_data.stream_url,
        location_lat=camera_data.location_lat,
        location_lng=camera_data.location_lng,
        is_active=camera_data.is_active,
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    return camera


def delete_camera(
    db: Session,
    camera_id: int,
) -> bool:
    camera = get_camera(db, camera_id)

    if camera is None:
        return False

    db.delete(camera)
    db.commit()

    return True