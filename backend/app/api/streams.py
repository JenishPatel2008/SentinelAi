from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import Camera
from ..database.schemas import StreamRequest
from ..video.stream_manager import stream_manager
from ..video.video_renderer import mjpeg_stream

router = APIRouter(prefix="/streams", tags=["Streams"])

@router.post("/start")
def start_stream(request: StreamRequest, db: Session = Depends(get_db)):
    camera = db.get(Camera, request.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    try:
        stream_manager.start(camera)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"camera_id": camera.id, "status": "started"}

@router.post("/stop")
def stop_stream(request: StreamRequest):
    stream_manager.stop(request.camera_id)
    return {"camera_id": request.camera_id, "status": "stopped"}

@router.get("/{camera_id}/status")
def stream_status(camera_id: int):
    return stream_manager.status(camera_id)

@router.get("/{camera_id}/mjpeg")
def stream_preview(camera_id: int):
    return StreamingResponse(mjpeg_stream(stream_manager, camera_id), media_type="multipart/x-mixed-replace; boundary=frame")
