from datetime import datetime
from pathlib import Path
import cv2
from sqlalchemy.orm import Session
from ..database.models import Alert, Event

EVIDENCE_DIR = Path("data/evidence")

def create_alert(db: Session, camera_id: int, track_id: int, object_type: str, confidence: float, zone: str, threat: dict, frame=None):
    """Persist one alert and optional annotated evidence frame."""
    now = datetime.utcnow()
    event = Event(camera_id=camera_id, event_type="intrusion", type="intrusion", severity=threat["severity"].lower(), description=threat["reason"], timestamp=now)
    db.add(event)
    db.flush()
    evidence_path = None
    if frame is not None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE_DIR / f"alert_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        cv2.imwrite(str(target), frame)
        evidence_path = f"/evidence/{target.name}"
    alert = Alert(event_id=event.id, camera_id=camera_id, track_id=track_id, object_type=object_type, zone=zone, score=threat["score"], reason=threat["reason"], evidence_path=evidence_path, severity=threat["severity"], status="active", message=threat["reason"], created_at=now, timestamp=now)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
