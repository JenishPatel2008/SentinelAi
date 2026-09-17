from datetime import datetime
from pathlib import Path
import cv2
from sqlalchemy.orm import Session
from ..database.models import Alert, Camera, Event
from ..api.websocket import manager

EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "evidence"

def create_alert(db: Session, camera_id: int, track_id: int, object_type: str, confidence: float, zone: str, threat: dict, frame=None, zone_type=None, plate_info=None):
    """Persist one alert and optional annotated evidence frame."""
    now = datetime.utcnow()
    plate_info = plate_info or {}
    event = Event(camera_id=camera_id, event_type="intrusion", severity=threat["severity"].lower(), description=threat["reason"], timestamp=now, plate_number=plate_info.get("plate_number"), plate_confidence=plate_info.get("plate_confidence"), watchlist_match=bool(plate_info.get("watchlist_match")))
    db.add(event)
    db.flush()
    evidence_path = None
    if frame is not None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE_DIR / f"alert_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        cv2.imwrite(str(target), frame)
        evidence_path = f"/evidence/{target.name}"
    alert = Alert(event_id=event.id, camera_id=camera_id, track_id=track_id, object_type=object_type, zone=zone, zone_type=zone_type, score=threat["score"], reason=threat["reason"], evidence_path=evidence_path, severity=threat["severity"], status="active", message=threat["reason"], created_at=now, timestamp=now, plate_number=plate_info.get("plate_number"), plate_confidence=plate_info.get("plate_confidence"), plate_observation_id=plate_info.get("plate_observation_id"), watchlist_match=bool(plate_info.get("watchlist_match")), watchlist_label=plate_info.get("watchlist_label"))
    db.add(alert)
    db.commit()
    db.refresh(alert)
    camera = db.get(Camera, camera_id)
    manager.broadcast_from_sync({
        "type": "alert",
        "data": {
            "id": alert.id, "camera_id": camera_id, "track_id": track_id,
            "object_type": object_type, "zone": zone, "zone_type": zone_type,
            "score": threat["score"], "severity": threat["severity"],
            "reason": threat["reason"], "status": alert.status,
            "alert_name": threat["reason"], "confidence": confidence,
            "plate_number": plate_info.get("plate_number"), "plate_confidence": plate_info.get("plate_confidence"),
            "watchlist_match": bool(plate_info.get("watchlist_match")), "watchlist_label": plate_info.get("watchlist_label"),
            "camera_name": camera.name if camera else f"Camera {camera_id}",
            "camera_code": camera.camera_code if camera else None,
            "evidence_path": evidence_path,
            "timestamp": now.isoformat(),
        },
    })
    return alert
