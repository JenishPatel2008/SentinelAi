from datetime import datetime
from pathlib import Path
import cv2
import json
from sqlalchemy.orm import Session
from ..database.models import Alert, Camera, Event, Incident
from ..api.websocket import manager

EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "evidence"

def _save_evidence(frame, prefix, timestamp):
    if frame is None:
        return None
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    target = EVIDENCE_DIR / f"{prefix}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    if not cv2.imwrite(str(target), frame):
        return None
    return f"/evidence/{target.name}"


def create_alert(db: Session, camera_id: int, track_id: int, object_type: str, confidence: float, zone: str, threat: dict, frame=None, zone_type=None, plate_info=None, night_info=None, vehicle_info=None, behavior_info=None, event_type=None, identity_info=None):
    """Persist one alert and optional annotated evidence frame."""
    now = datetime.utcnow()
    plate_info = plate_info or {}
    night_info = night_info or {}
    vehicle_info = vehicle_info or {}
    behavior_info = behavior_info or {}
    identity_info = identity_info or {}
    event_type = event_type or ("night_intrusion" if night_info.get("scene_condition") in {"NIGHT", "LOW_LIGHT"} else "intrusion")
    event = Event(camera_id=camera_id, event_type=event_type, severity=threat["severity"].lower(), description=threat["reason"], timestamp=now, plate_number=plate_info.get("plate_number"), plate_confidence=plate_info.get("plate_confidence"), watchlist_match=bool(plate_info.get("watchlist_match")), track_id=track_id, object_type=object_type, zone=zone, zone_type=zone_type, scene_condition=night_info.get("scene_condition"), night_confidence=night_info.get("night_confidence"), movement_distance=night_info.get("movement_distance"), vehicle_class=vehicle_info.get("vehicle_class"), vehicle_class_confidence=vehicle_info.get("vehicle_class_confidence"))
    event.behavior_type = behavior_info.get("behavior_type")
    event.behavior_state = behavior_info.get("behavior_state")
    event.behavior_reason = behavior_info.get("behavior_reason")
    event.behavior_metadata = json.dumps(behavior_info) if behavior_info else None
    event.duration_seconds = behavior_info.get("duration_seconds")
    event.identity_status = identity_info.get("identity_status")
    event.subject_id = identity_info.get("subject_id")
    event.subject_label = identity_info.get("subject_label")
    event.subject_category = identity_info.get("subject_category")
    event.face_status = identity_info.get("face_status")
    event.face_confidence = identity_info.get("face_confidence")
    event.face_similarity = identity_info.get("face_similarity")
    event.face_bbox = json.dumps(identity_info.get("face_bbox")) if identity_info.get("face_bbox") else None
    db.add(event)
    db.flush()
    evidence_path = None
    if frame is not None:
        evidence_path = _save_evidence(frame, "alert", now)
        event.evidence_path = evidence_path
    alert = Alert(event_id=event.id, camera_id=camera_id, track_id=track_id, object_type=object_type, zone=zone, zone_type=zone_type, score=threat["score"], reason=threat["reason"], evidence_path=evidence_path, severity=threat["severity"], status="active", message=threat["reason"], created_at=now, timestamp=now, plate_number=plate_info.get("plate_number"), plate_confidence=plate_info.get("plate_confidence"), plate_observation_id=plate_info.get("plate_observation_id"), watchlist_match=bool(plate_info.get("watchlist_match")), watchlist_label=plate_info.get("watchlist_label"), scene_condition=night_info.get("scene_condition"), night_confidence=night_info.get("night_confidence"), movement_distance=night_info.get("movement_distance"), vehicle_class=vehicle_info.get("vehicle_class"), vehicle_class_confidence=vehicle_info.get("vehicle_class_confidence"))
    alert.behavior_type = behavior_info.get("behavior_type")
    alert.behavior_state = behavior_info.get("behavior_state")
    alert.behavior_reason = behavior_info.get("behavior_reason")
    alert.behavior_metadata = json.dumps(behavior_info) if behavior_info else None
    alert.behavior_duration_seconds = behavior_info.get("duration_seconds")
    alert.identity_status = identity_info.get("identity_status")
    alert.subject_id = identity_info.get("subject_id")
    alert.subject_label = identity_info.get("subject_label")
    alert.subject_category = identity_info.get("subject_category")
    alert.face_status = identity_info.get("face_status")
    alert.face_confidence = identity_info.get("face_confidence")
    alert.face_similarity = identity_info.get("face_similarity")
    alert.face_bbox = json.dumps(identity_info.get("face_bbox")) if identity_info.get("face_bbox") else None
    if identity_info.get("protected_zone"):
        alert.alarm_status = "ACTIVE"
    db.add(alert)
    db.commit()
    db.refresh(alert)
    if identity_info.get("protected_zone"):
        incident = Incident(incident_code=f"INC-{now.strftime('%Y%m%d')}-{alert.id:04d}", alert_id=alert.id, camera_id=camera_id, title="Potential Unauthorized Intrusion", status="open", created_at=now, updated_at=now)
        db.add(incident)
        db.commit()
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
            "event_type": event.event_type, "scene_condition": night_info.get("scene_condition"),
            "night_confidence": night_info.get("night_confidence"), "movement_distance": night_info.get("movement_distance"),
            "vehicle_class": vehicle_info.get("vehicle_class"), "vehicle_class_confidence": vehicle_info.get("vehicle_class_confidence"),
            "behavior_type": behavior_info.get("behavior_type"), "behavior_state": behavior_info.get("behavior_state"),
            "behavior_reason": behavior_info.get("behavior_reason"), "behavior_duration_seconds": behavior_info.get("duration_seconds"),
            "identity_status": identity_info.get("identity_status"), "subject_id": identity_info.get("subject_id"),
            "subject_label": identity_info.get("subject_label"), "subject_category": identity_info.get("subject_category"),
            "face_status": identity_info.get("face_status"), "face_confidence": identity_info.get("face_confidence"),
            "face_similarity": identity_info.get("face_similarity"), "alarm_status": alert.alarm_status,
            "camera_name": camera.name if camera else f"Camera {camera_id}",
            "camera_code": camera.camera_code if camera else None,
            "evidence_path": evidence_path,
            "timestamp": now.isoformat(),
        },
    })
    return alert


def create_behavior_alert(db: Session, camera_id: int, track: dict, behavior: dict, threat: dict, frame=None):
    """Persist one explainable temporal behavior signal and notify connected clients."""
    zone = track.get("zone_matches", [{}])[0] if track.get("zone_matches") else {}
    behavior_info = {**behavior, "behavior_type": behavior.get("behavior_type"), "behavior_state": behavior.get("behavior_state"), "behavior_reason": behavior.get("behavior_reason")}
    return create_alert(
        db,
        camera_id,
        behavior.get("track_id", track.get("track_id")),
        behavior.get("object_type", track.get("class", "object")),
        track.get("confidence", 0),
        behavior.get("zone") or zone.get("name") or "Behavior signal",
        threat,
        frame,
        behavior.get("zone_type") or zone.get("zone_type"),
        vehicle_info={
            "vehicle_class": behavior.get("vehicle_class") or track.get("vehicle_class"),
            "vehicle_class_confidence": behavior.get("vehicle_class_confidence") or track.get("vehicle_class_confidence"),
        },
        night_info={
            "scene_condition": behavior.get("scene_condition"),
            "night_confidence": behavior.get("night_confidence"),
        },
        behavior_info=behavior_info,
        event_type=behavior.get("behavior_type", "behavior").lower(),
    )


def create_face_event(db: Session, camera_id: int, event_info: dict, frame=None):
    """Persist a rate-limited identity lifecycle event without exposing embeddings."""
    now = event_info.get("timestamp") or datetime.utcnow()
    evidence_path = _save_evidence(frame, "face", now)
    event = Event(
        camera_id=camera_id,
        event_type=event_info["event_type"].lower(),
        severity="low",
        description=event_info.get("reason"),
        timestamp=now,
        track_id=event_info.get("track_id"),
        object_type="person",
        zone=event_info.get("zone"),
        zone_type=event_info.get("zone_type"),
        scene_condition=event_info.get("scene_condition"),
        night_confidence=event_info.get("night_confidence"),
        identity_status=event_info.get("identity_status"),
        subject_id=event_info.get("subject_id"),
        subject_label=event_info.get("subject_label"),
        subject_category=event_info.get("subject_category"),
        face_status=event_info.get("face_status"),
        face_confidence=event_info.get("face_confidence"),
        face_similarity=event_info.get("face_similarity"),
        face_bbox=json.dumps(event_info.get("face_bbox")) if event_info.get("face_bbox") else None,
        evidence_path=evidence_path,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    camera = db.get(Camera, camera_id)
    manager.broadcast_from_sync({
        "type": "event",
        "data": {
            "id": event.id, "event_type": event.event_type, "camera_id": camera_id,
            "camera_name": camera.name if camera else f"Camera {camera_id}", "track_id": event.track_id,
            "object_type": event.object_type, "zone": event.zone, "identity_status": event.identity_status,
            "subject_id": event.subject_id, "subject_label": event.subject_label,
            "subject_category": event.subject_category, "face_status": event.face_status,
            "face_confidence": event.face_confidence, "face_similarity": event.face_similarity,
            "evidence_path": event.evidence_path, "timestamp": now.isoformat(),
        },
    })
    return event


def create_night_movement_event(db: Session, camera_id: int, track: dict, scene: dict, frame=None):
    """Persist one rate-limited low-light movement event without creating an alert."""
    now = datetime.utcnow()
    zone = track.get("zone_matches", [{}])[0] if track.get("zone_matches") else {}
    evidence_path = None
    if frame is not None:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE_DIR / f"night_movement_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        if cv2.imwrite(str(target), frame):
            evidence_path = f"/evidence/{target.name}"
    event = Event(
        camera_id=camera_id,
        event_type="night_movement",
        severity="low",
        description=f"{track.get('class', 'Object').title()} moving during {scene.get('scene_condition', 'LOW_LIGHT').replace('_', ' ').lower()} conditions",
        timestamp=now,
        track_id=track.get("track_id"),
        object_type=track.get("class"),
        zone=zone.get("name"),
        zone_type=zone.get("zone_type"),
        scene_condition=scene.get("scene_condition"),
        night_confidence=scene.get("night_confidence"),
        movement_distance=track.get("movement_distance"),
        vehicle_class=track.get("vehicle_class"),
        vehicle_class_confidence=track.get("vehicle_class_confidence"),
        evidence_path=evidence_path,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    camera = db.get(Camera, camera_id)
    manager.broadcast_from_sync({
        "type": "event",
        "data": {
            "id": event.id, "event_type": event.event_type, "camera_id": camera_id,
            "camera_name": camera.name if camera else f"Camera {camera_id}",
            "track_id": event.track_id, "object_type": event.object_type,
            "zone": event.zone, "scene_condition": event.scene_condition,
            "night_confidence": event.night_confidence,
            "movement_distance": event.movement_distance, "evidence_path": evidence_path,
            "vehicle_class": event.vehicle_class, "vehicle_class_confidence": event.vehicle_class_confidence,
            "timestamp": now.isoformat(),
        },
    })
    return event
