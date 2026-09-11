from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
import json
from queue import Empty, Full, Queue
import time

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
        state = {"camera_id": camera.id, "status": "starting", "error": None, "source": source, "stop": Event(), "latest": None, "last_frame_at": None, "frame_queue": Queue(maxsize=1), "reader_ready": Event(), "reader_error": None, "frames_processed": 0, "detections": 0, "tracks": set(), "alerts": 0}
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
        db = SessionLocal()
        reader = Thread(target=self._capture_reader, args=(state, source, source_type), daemon=True, name=f"sentinel-reader-{camera_id}")
        reader.start()
        try:
            if not state["reader_ready"].wait(timeout=5):
                state["status"] = "offline"
                state["error"] = state["reader_error"] or "Camera source did not become ready"
                return
            if state["reader_error"]:
                state["status"] = "offline"
                state["error"] = state["reader_error"]
                return

            self._set_camera_status(db, camera_id, "starting")
            zones = [{"id": zone.id, "name": zone.name, "zone_type": zone.zone_type, "polygon_points": json.loads(zone.polygon_points), "enabled": zone.enabled} for zone in db.query(Zone).filter(Zone.camera_id == camera_id, Zone.enabled.is_(True)).all()]
            pipeline = DetectionPipeline(str(PROJECT_ROOT / "ai_models" / "yolo" / "model.pt"), .45, zones)
            state["status"] = "online"
            self._set_camera_status(db, camera_id, "online")
            alerted_tracks = set()

            while not state["stop"].is_set():
                try:
                    frame = state["frame_queue"].get(timeout=.5)
                except Empty:
                    if state["reader_error"]:
                        state["status"] = "offline"
                        state["error"] = state["reader_error"]
                        break
                    continue

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
            state["stop"].set()
            reader.join(timeout=1)
            self._set_camera_status(db, camera_id, "offline")
            db.close()
            if state["status"] != "error":
                state["status"] = "offline"

    @staticmethod
    def _capture_reader(state, source, source_type):
        capture = cv2.VideoCapture(source)
        try:
            if not capture.isOpened():
                state["reader_error"] = f"Unable to open video source: {source}"
                return
            source_fps = capture.get(cv2.CAP_PROP_FPS)
            frame_delay = 1 / source_fps if 0 < source_fps <= 60 else .03
            state["reader_ready"].set()
            while not state["stop"].is_set():
                ok, frame = capture.read()
                if not ok:
                    if source_type == "video":
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(.02)
                        continue
                    state["reader_error"] = "Camera source stopped returning frames"
                    return

                encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                if encoded_ok:
                    state["latest"] = encoded.tobytes()
                    state["last_frame_at"] = time.monotonic()
                try:
                    state["frame_queue"].put_nowait(frame)
                except Full:
                    try:
                        state["frame_queue"].get_nowait()
                    except Empty:
                        pass
                    try:
                        state["frame_queue"].put_nowait(frame)
                    except Full:
                        pass
                time.sleep(frame_delay)
        finally:
            capture.release()
            state["reader_ready"].set()

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
        status = state["status"]
        if status == "online" and state["last_frame_at"] and time.monotonic() - state["last_frame_at"] > 20:
            status = "stalled"
        return {"camera_id": camera_id, "status": status, "error": state["error"] or ("No processed frame received recently" if status == "stalled" else None), "frames_processed": state["frames_processed"], "detections": state["detections"], "tracks": len(state["tracks"]), "alerts": state["alerts"]}

    def latest_frame(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        return state.get("latest") if state else None


stream_manager = StreamManager()
