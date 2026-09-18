from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Alert
from ..services.alarm_service import alarm_service


router = APIRouter(prefix="/alarms", tags=["Alarms"])


def _state(alert):
    current = alarm_service.get_status(alert.id)
    return current or {"alert_id": alert.id, "camera_id": alert.camera_id, "track_id": alert.track_id, "zone": alert.zone, "status": alert.alarm_status or "INACTIVE", "reason": alert.reason}


@router.get("/{alert_id}")
def get_alarm(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    return _state(alert)


def _change(alert_id, status, db):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    alert.alarm_status = status
    db.commit()
    updated = alarm_service.set_status(alert_id, status) or _state(alert)
    from ..api.websocket import manager
    manager.broadcast_from_sync({"type": "alarm_state", "data": {**updated, "alarm_status": status}})
    return updated


@router.post("/{alert_id}/acknowledge")
def acknowledge_alarm(alert_id: int, db: Session = Depends(get_db)):
    return _change(alert_id, "ACKNOWLEDGED", db)


@router.post("/{alert_id}/silence")
def silence_alarm(alert_id: int, db: Session = Depends(get_db)):
    return _change(alert_id, "SILENCED", db)
