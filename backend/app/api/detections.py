from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import Detection
from ..database.schemas import DetectionResponse

router = APIRouter(prefix="/detections", tags=["Detections"])

@router.get("", response_model=list[DetectionResponse])
def list_detections(db: Session = Depends(get_db)):
    return db.query(Detection).order_by(Detection.timestamp.desc()).limit(500).all()
