from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from ..database.database import get_db
from ..database.models import Alert, Detection, Event
from ..database.schemas import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("", response_model=AnalyticsResponse)
def analytics(db: Session = Depends(get_db)):
    vehicle_types = {"car", "truck", "motorcycle", "bus", "bicycle"}
    vehicle_filter = or_(Detection.category == "vehicle", Detection.object_type.in_(vehicle_types))
    total_vehicles = db.query(func.count(Detection.id)).filter(vehicle_filter).scalar() or 0
    known_vehicle_counts = {
        name: db.query(func.count(Detection.id)).filter(vehicle_filter, func.coalesce(Detection.vehicle_class, Detection.object_type) == name).scalar() or 0
        for name in vehicle_types
    }
    behavior_counts = {
        "LOITERING": db.query(func.count(Event.id)).filter(Event.behavior_type == "LOITERING").scalar() or 0,
        "REPEATED_FENCE_CROSSING": db.query(func.count(Event.id)).filter(Event.behavior_type == "REPEATED_FENCE_CROSSING").scalar() or 0,
        "EXTENDED_RESTRICTED_PRESENCE": db.query(func.count(Event.id)).filter(Event.behavior_type == "EXTENDED_RESTRICTED_PRESENCE").scalar() or 0,
        "PROLONGED_STATIONARY": db.query(func.count(Event.id)).filter(Event.behavior_type == "PROLONGED_STATIONARY").scalar() or 0,
        "PERSON_VEHICLE_PROXIMITY": db.query(func.count(Event.id)).filter(Event.behavior_type == "PERSON_VEHICLE_PROXIMITY").scalar() or 0,
    }
    suspicious_activities = sum(behavior_counts.values())
    return AnalyticsResponse(
        total_detections=db.query(func.count(Detection.id)).scalar() or 0,
        active_alerts=db.query(func.count(Alert.id)).filter(Alert.status == "active").scalar() or 0,
        critical_alerts=db.query(func.count(Alert.id)).filter(Alert.severity == "CRITICAL").scalar() or 0,
        total_events=db.query(func.count(Event.id)).scalar() or 0,
        night_movements=db.query(func.count(Event.id)).filter(Event.event_type == "night_movement").scalar() or 0,
        night_intrusions=db.query(func.count(Event.id)).filter(Event.event_type == "night_intrusion").scalar() or 0,
        night_vehicle_movements=db.query(func.count(Event.id)).filter(Event.event_type == "night_movement", Event.object_type.in_({"car", "truck", "motorcycle", "bus", "bicycle"})).scalar() or 0,
        total_vehicles=total_vehicles,
        cars=known_vehicle_counts["car"],
        motorcycles=known_vehicle_counts["motorcycle"],
        buses=known_vehicle_counts["bus"],
        trucks=known_vehicle_counts["truck"],
        bicycles=known_vehicle_counts["bicycle"],
        unknown_vehicles=max(0, total_vehicles - sum(known_vehicle_counts.values())),
        suspicious_activities=suspicious_activities,
        loitering=behavior_counts["LOITERING"],
        repeated_fence_crossings=behavior_counts["REPEATED_FENCE_CROSSING"],
        extended_restricted_presence=behavior_counts["EXTENDED_RESTRICTED_PRESENCE"],
        prolonged_stationary=behavior_counts["PROLONGED_STATIONARY"],
        person_vehicle_proximity=behavior_counts["PERSON_VEHICLE_PROXIMITY"],
        night_suspicious_events=db.query(func.count(Event.id)).filter(Event.behavior_type.is_not(None), Event.scene_condition.in_({"NIGHT", "LOW_LIGHT"})).scalar() or 0,
    )
