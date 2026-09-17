from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.database import get_db
from ..database.models import Alert, Detection, Event
from ..database.schemas import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    return AnalyticsResponse(
        total_detections=db.query(func.count(Detection.id)).scalar() or 0,
        active_alerts=db.query(func.count(Alert.id)).filter(Alert.status == "active").scalar() or 0,
        critical_alerts=db.query(func.count(Alert.id)).filter(Alert.severity == "CRITICAL").scalar() or 0,
        total_events=db.query(func.count(Event.id)).scalar() or 0,
        night_movements=db.query(func.count(Event.id)).filter(Event.event_type == "night_movement").scalar() or 0,
        night_intrusions=db.query(func.count(Event.id)).filter(Event.event_type == "night_intrusion").scalar() or 0,
        night_vehicle_movements=db.query(func.count(Event.id)).filter(Event.event_type == "night_movement", Event.object_type.in_({"car", "truck", "motorcycle", "bus", "bicycle"})).scalar() or 0,
    )
