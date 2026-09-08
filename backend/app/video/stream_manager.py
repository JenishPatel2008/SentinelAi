from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
import json

import cv2

from ..ai.pipeline import DetectionPipeline
from ..ai.zone_detector import annotate_zones, zones_for_frame
from ..database.database import PROJECT_ROOT, SessionLocal
from ..database.models import Camera, Detection, Zone
from ..services.alert_service import create_alert


class StreamManager:
    """Own camera workers and the latest browser-consumable JPEG frame."""

    def __init__(self):
        self.streams = {}
        self.lock = Lock()

    @staticmethod
    def resolve_source(source, source_type="video"):
        if source_type == "webcam":
            return int(source) if str(source).isdigit() else source
        if "://" in source:
            return source
        path = Path(source)
        return str(path if path.is_absolute() else PROJECT_ROOT / path)

    def start(self, camera):
        source = camera.stream_url
        if not source:
            raise ValueError("Camera has no video source configured")

        resolved_source = self.resolve_source(source, camera.source_type)
        if isinstance(resolved_source, str) and not resolved_source.startswith(("rtsp://", "http://", "https://")) and not Path(resolved_source).exists():
            raise ValueError(f"Unable to find video source: {resolved_source}")

        self.stop(camera.id)
        state = {"camera_id": camera.id, "status": "starting", "error": None, "source": source, "stop": Event(), "latest": None, "frames_processed": 0, "detections": 0, "tracks": set(), "alerts": 0}
        thread = Thread(target=self._worker, args=(state, resolved_source, camera.source_type), daemon=True, name=f"sentinel-camera-{camera.id}")
        state["thread"] = thread
        with self.lock:
            self.streams[camera.id] = state
        thread.start()

    def stop(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        if state:
            state["stop"].set()
            if state["status"] == "online":
                state["status"] = "stopping"

    def _worker(self, state, source, source_type):
        camera_id = state["camera_id"]
        capture = cv2.VideoCapture(source)
        db = SessionLocal()
        try:
            if not capture.isOpened():
                state["status"] = "offline"
                return

            state["status"] = "online"
            self._set_camera_status(db, camera_id, "online")
            zones = [{"id": zone.id, "name": zone.name, "zone_type": zone.zone_type, "polygon_points": json.loads(zone.polygon_points), "enabled": zone.enabled} for zone in db.query(Zone).filter(Zone.camera_id == camera_id, Zone.enabled.is_(True)).all()]
            pipeline = DetectionPipeline(str(PROJECT_ROOT / "ai_models" / "yolo" / "model.pt"), .45, zones)
            alerted_tracks = set()

            while not state["stop"].is_set():
                ok, frame = capture.read()
                if not ok:
                    if source_type == "video":
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        pipeline.tracker.tracks.clear()
                        continue
                    state["status"] = "offline"
                    break

                tracks, threat = pipeline.process(frame)
                state["frames_processed"] += 1
                state["detections"] += len(tracks)
                state["tracks"].update(track["track_id"] for track in tracks)
                now = datetime.utcnow()
                for track in tracks:
                    db.add(Detection(camera_id=camera_id, track_id=track["track_id"], object_type=track["class"], confidence=track["confidence"], timestamp=now))

                display = annotate_zones(frame.copy(), zones_for_frame(zones, frame.shape[1], frame.shape[0]))
                for track in tracks:
                    x1, y1, x2, y2 = map(int, track["bbox"])
                    color = (0, 180, 255) if track.get("intrusion") else (80, 210, 120)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(display, f"{track['class']} #{track['track_id']} {track['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2)

                intruder = next((track for track in tracks if track.get("intrusion")), None)
                if intruder and threat["score"] >= 61 and intruder["track_id"] not in alerted_tracks:
                    alerted_tracks.add(intruder["track_id"])
                    zone = intruder["zone_matches"][0]
                    create_alert(db, camera_id, intruder["track_id"], intruder["class"], intruder["confidence"], zone["name"], threat, display, zone["zone_type"])
                    state["alerts"] += 1

                db.commit()
                ok, encoded = cv2.imencode(".jpg", display, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok:
                    state["latest"] = encoded.tobytes()
        except Exception as error:
            state["status"] = "error"
            state["error"] = str(error)
            db.rollback()
        finally:
            capture.release()
            self._set_camera_status(db, camera_id, "offline")
            db.close()
            if state["status"] != "error":
                state["status"] = "offline"
            state["stop"].set()

    @staticmethod
    def _set_camera_status(db, camera_id, status):
        camera = db.get(Camera, camera_id)
        if camera:
            camera.status = status
            db.commit()

    def status(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        if not state:
            return {"camera_id": camera_id, "status": "offline", "frames_processed": 0, "detections": 0, "tracks": 0, "alerts": 0}
        return {"camera_id": camera_id, "status": state["status"], "error": state["error"], "frames_processed": state["frames_processed"], "detections": state["detections"], "tracks": len(state["tracks"]), "alerts": state["alerts"]}

    def latest_frame(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        return state.get("latest") if state else None


stream_manager = StreamManager()
