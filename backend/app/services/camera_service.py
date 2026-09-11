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
        source_type=camera_data.source_type,
        status=camera_data.status,
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

    from ..video.stream_manager import stream_manager

    stream_manager.stop(camera_id)
    db.delete(camera)
    db.commit()

    return True


def update_camera(db: Session, camera_id: int, values: dict) -> Camera | None:
    camera = get_camera(db, camera_id)
    if camera is None:
        return None
    if values.get("is_active") is False or values.get("stream_url") not in (None, camera.stream_url):
        from ..video.stream_manager import stream_manager

        stream_manager.stop(camera_id)
    for key, value in values.items():
        if value is not None:
            setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return camera
