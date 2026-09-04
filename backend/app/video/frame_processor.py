from datetime import datetime
import cv2
from sqlalchemy.orm import Session
from ..ai.pipeline import DetectionPipeline
import json
from ..ai.zone_detector import annotate_zones
from ..database.models import Detection
from ..database.models import Zone
from ..services.alert_service import create_alert

def process_video(camera, db: Session, model_path="ai_models/yolo/model.pt", confidence=.45, max_frames=None):
    """Run a finite MP4 through detection; returns a summary and stops at EOF."""
    if not camera.stream_url:
        raise ValueError("Camera has no video source configured")
    capture = cv2.VideoCapture(camera.stream_url)
    if not capture.isOpened():
        raise ValueError(f"Unable to open video source: {camera.stream_url}")
    zones = [
        {"id": zone.id, "name": zone.name, "zone_type": zone.zone_type,
         "polygon_points": json.loads(zone.polygon_points), "enabled": zone.enabled}
        for zone in db.query(Zone).filter(Zone.camera_id == camera.id, Zone.enabled.is_(True)).all()
    ]
    pipeline = DetectionPipeline(model_path, confidence, zones)
    processed = alerts = 0
    try:
        while max_frames is None or processed < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            tracks, threat = pipeline.process(frame)
            now = datetime.utcnow()
            for track in tracks:
                db.add(Detection(camera_id=camera.id, track_id=track["track_id"], object_type=track["class"], confidence=track["confidence"], timestamp=now))
            intruder = next((track for track in tracks if track.get("intrusion")), None)
            if intruder and threat["score"] >= 61 and intruder["track_id"] not in pipeline.__dict__.setdefault("alerted", set()):
                pipeline.alerted.add(intruder["track_id"])
                evidence = annotate_zones(frame.copy(), pipeline.zones)
                x1, y1, x2, y2 = map(int, intruder["bbox"])
                cv2.rectangle(evidence, (x1, y1), (x2, y2), (0, 180, 255), 2)
                cv2.putText(evidence, f"Person #{intruder['track_id']} {threat['severity']}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 180, 255), 2)
                zone_name = intruder["zone_matches"][0]["name"]
                create_alert(db, camera.id, intruder["track_id"], intruder["class"], intruder["confidence"], zone_name, threat, evidence, intruder["zone_matches"][0]["zone_type"])
                alerts += 1
            processed += 1
        db.commit()
    finally:
        capture.release()
    return {"frames_processed": processed, "alerts_created": alerts}
