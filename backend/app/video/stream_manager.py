from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
import json
from queue import Empty, Full, Queue
import time

import cv2

from ..ai.pipeline import DetectionPipeline
from ..ai.zone_detector import annotate_zones, zones_for_frame
from ..core.config import get_runtime_settings
from ..database.database import PROJECT_ROOT, SessionLocal
from ..database.models import Camera, Detection, Zone
from ..services.alert_service import create_alert
from ..utils.urls import validate_rtsp_url


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

    @staticmethod
    def is_rtsp(source, source_type):
        return source_type == "rtsp" or str(source).lower().startswith("rtsp://")

    @staticmethod
    def is_looping_file(source_type):
        return source_type in {"video", "mp4"}

    @staticmethod
    def rtsp_connection_error():
        return "Unable to connect to RTSP camera. Check the camera IP, RTSP URL, credentials, and network connection."

    @staticmethod
    def test_connection(source):
        validate_rtsp_url(source)
        capture = cv2.VideoCapture(source)
        try:
            return bool(capture.isOpened() and capture.read()[0])
        finally:
            capture.release()

    def start(self, camera):
        source = camera.stream_url
        if not source:
            raise ValueError("Camera has no video source configured")

        with self.lock:
            existing = self.streams.get(camera.id)
        if existing and existing["thread"].is_alive() and not existing["stop"].is_set():
            return

        if camera.source_type == "rtsp":
            validate_rtsp_url(source)

        resolved_source = self.resolve_source(source, camera.source_type)
        if isinstance(resolved_source, str) and not resolved_source.startswith(("rtsp://", "http://", "https://")) and not Path(resolved_source).exists():
            raise ValueError("Unable to find the configured video source.")

        self.stop(camera.id)
        state = {"camera_id": camera.id, "status": "starting", "error": None, "source": source, "stop": Event(), "latest": None, "last_frame_at": None, "frame_queue": Queue(maxsize=1), "reader_ready": Event(), "reader_error": None, "source_cycle": 0, "frames_processed": 0, "detections": 0, "tracks": set(), "alerts": 0}
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
            if state["status"] in {"starting", "connecting", "online"}:
                state["status"] = "stopping"
            thread = state.get("thread")
            if thread and thread is not current_thread() and thread.is_alive():
                thread.join(timeout=2)

    def stop_all(self):
        with self.lock:
            states = list(self.streams.values())
        for state in states:
            state["stop"].set()
        for state in states:
            thread = state.get("thread")
            if thread and thread is not current_thread() and thread.is_alive():
                thread.join(timeout=2)

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
            if state["reader_error"] and source_type != "rtsp":
                state["status"] = "offline"
                state["error"] = state["reader_error"]
                return

            self._set_camera_status(db, camera_id, "starting")
            zones = [{"id": zone.id, "name": zone.name, "zone_type": zone.zone_type, "polygon_points": json.loads(zone.polygon_points), "enabled": zone.enabled} for zone in db.query(Zone).filter(Zone.camera_id == camera_id, Zone.enabled.is_(True)).all()]
            settings = get_runtime_settings()
            vehicle_classes = {"car", "truck", "motorcycle", "bus", "bicycle"}
            pipeline = DetectionPipeline(
                str(PROJECT_ROOT / "ai_models" / "yolo" / "model.pt"),
                min(settings["detection_confidence"], settings["vehicle_confidence"]),
                zones,
                class_confidences={"person": settings["detection_confidence"], **{item: settings["vehicle_confidence"] for item in vehicle_classes}},
            )
            camera_status = "starting"
            self._set_camera_status(db, camera_id, camera_status)
            alerted_tracks = set()
            source_cycle = state["source_cycle"]

            while not state["stop"].is_set():
                try:
                    frame = state["frame_queue"].get(timeout=.5)
                except Empty:
                    if state["status"] != camera_status:
                        camera_status = state["status"]
                        self._set_camera_status(db, camera_id, camera_status)
                    if state["reader_error"] and source_type != "rtsp":
                        state["status"] = "offline"
                        state["error"] = state["reader_error"]
                        break
                    continue

                if camera_status != "online":
                    camera_status = "online"
                    state["status"] = "online"
                    state["error"] = None
                    self._set_camera_status(db, camera_id, camera_status)

                if state["source_cycle"] != source_cycle:
                    pipeline.reset()
                    alerted_tracks.clear()
                    source_cycle = state["source_cycle"]

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
                if intruder and intruder["track_id"] not in alerted_tracks:
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
            with self.lock:
                is_current = self.streams.get(camera_id) is state
            if is_current:
                self._set_camera_status(db, camera_id, "offline")
            db.close()
            if state["status"] != "error":
                state["status"] = "offline"

    @staticmethod
    def _capture_reader(state, source, source_type):
        retry_delay = 1
        while not state["stop"].is_set():
            capture = cv2.VideoCapture(source)
            if not capture.isOpened():
                capture.release()
                state["status"] = "offline"
                state["error"] = StreamManager.rtsp_connection_error() if source_type == "rtsp" else "Unable to open video source."
                state["reader_error"] = state["error"]
                state["reader_ready"].set()
                if source_type != "rtsp" or state["stop"].wait(retry_delay):
                    return
                retry_delay = min(retry_delay * 2, 30)
                continue

            try:
                state["reader_error"] = None
                state["error"] = None
                state["status"] = "connecting"
                state["reader_ready"].set()
                retry_delay = 1
                source_fps = capture.get(cv2.CAP_PROP_FPS)
                frame_delay = 1 / source_fps if 0 < source_fps <= 60 else .03
                while not state["stop"].is_set():
                    ok, frame = capture.read()
                    if not ok:
                        if StreamManager.is_looping_file(source_type):
                            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            state["source_cycle"] += 1
                            time.sleep(.02)
                            continue
                        state["status"] = "offline"
                        state["error"] = StreamManager.rtsp_connection_error() if source_type == "rtsp" else "Camera source stopped returning frames."
                        state["reader_error"] = state["error"]
                        break

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

            if source_type != "rtsp" or state["stop"].is_set():
                return
            if state["stop"].wait(retry_delay):
                return
            retry_delay = min(retry_delay * 2, 30)

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
