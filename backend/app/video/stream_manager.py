from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
import json
from queue import Empty, Full, Queue
import time

import cv2

from ..ai.pipeline import DetectionPipeline
from ..ai.anpr import ANPREngine
from ..ai.night_detector import NightDetector
from ..ai.threat_engine import calculate_threat
from ..ai.zone_detector import annotate_zones, zones_for_frame
from ..core.config import get_runtime_settings
from ..database.database import PROJECT_ROOT, SessionLocal
from ..database.models import Camera, Detection, PlateObservation, WatchlistEntry, Zone
from ..api.websocket import manager
from ..services.alert_service import create_alert, create_night_movement_event
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
        state = {"camera_id": camera.id, "status": "starting", "error": None, "source": source, "stop": Event(), "latest": None, "last_frame_at": None, "frame_queue": Queue(maxsize=1), "reader_ready": Event(), "reader_error": None, "source_cycle": 0, "frames_processed": 0, "detections": 0, "tracks": set(), "alerts": 0, "scene": {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}, "moving_tracks": 0, "night_events": 0}
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
                movement_threshold=settings.get("movement_threshold", 12),
            )
            anpr = ANPREngine(
                sample_interval=settings.get("anpr_frame_interval", 5),
                min_confidence=settings.get("anpr_min_ocr_confidence", .55),
            )
            night_detector = NightDetector(
                night_threshold=settings.get("night_brightness_threshold", 60),
                low_light_threshold=settings.get("low_light_brightness_threshold", 100),
                night_confirmation_frames=settings.get("night_confirmation_frames", 5),
                day_confirmation_frames=settings.get("day_confirmation_frames", 5),
            )
            watchlist_entries = db.query(WatchlistEntry).filter(WatchlistEntry.enabled.is_(True)).all()
            watchlist = {entry.plate_number: entry for entry in watchlist_entries}
            camera_status = "starting"
            self._set_camera_status(db, camera_id, camera_status)
            alerted_tracks = set()
            night_event_times = {}
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
                    anpr.reset()
                    night_detector.reset()
                    alerted_tracks.clear()
                    night_event_times.clear()
                    source_cycle = state["source_cycle"]

                tracks, threat = pipeline.process(frame)
                state["frames_processed"] += 1
                scene = night_detector.analyze(frame)
                state["scene"] = scene
                for track in tracks:
                    track["scene_condition"] = scene["scene_condition"]
                    track["night_confidence"] = scene["night_confidence"]
                night_movements = [track for track in tracks if scene["scene_condition"] in {"NIGHT", "LOW_LIGHT"} and track.get("moving")]
                state["moving_tracks"] = len([track for track in tracks if track.get("moving")])
                if state["frames_processed"] % 15 == 0:
                    manager.broadcast_from_sync({
                        "type": "scene",
                        "data": {"camera_id": camera_id, **scene, "moving_tracks": state["moving_tracks"], "timestamp": datetime.utcnow().isoformat()},
                    })
                tracks, plate_observations = anpr.observe(
                    frame,
                    tracks,
                    camera_id,
                    frame_index=state["frames_processed"],
                    timestamp=datetime.utcnow(),
                    watchlist=watchlist,
                ) if settings.get("anpr_enabled", True) else (tracks, [])
                state["detections"] += len(tracks)
                state["tracks"].update(track["track_id"] for track in tracks)
                now = datetime.utcnow()
                for track in tracks:
                    db.add(Detection(camera_id=camera_id, track_id=track["track_id"], object_type=track["class"], confidence=track["confidence"], timestamp=now))

                observation_rows = {}
                for observation in plate_observations:
                    original_path = self._save_anpr_crop(observation["original_crop"], camera_id, observation["track_id"], "original", now)
                    processed_path = self._save_anpr_crop(observation["processed_crop"], camera_id, observation["track_id"], "processed", now)
                    row = PlateObservation(
                        camera_id=camera_id,
                        track_id=observation["track_id"],
                        vehicle_type=observation["vehicle_type"],
                        vehicle_confidence=observation["vehicle_confidence"],
                        plate_bbox=json.dumps(observation["plate_bbox"]),
                        plate_number=observation["plate_number"],
                        plate_confidence=observation["plate_confidence"],
                        detection_confidence=observation["detection_confidence"],
                        ocr_confidence=observation["ocr_confidence"],
                        original_crop_path=original_path,
                        processed_crop_path=processed_path,
                        watchlist_id=observation["watchlist_id"],
                        timestamp=observation["timestamp"],
                    )
                    db.add(row)
                    db.flush()
                    observation_rows[observation["track_id"]] = row
                    manager.broadcast_from_sync({
                        "type": "anpr",
                        "data": {
                            "camera_id": camera_id,
                            "track_id": observation["track_id"],
                            "vehicle_type": observation["vehicle_type"],
                            "plate_number": observation["plate_number"],
                            "plate_confidence": observation["plate_confidence"],
                            "detection_confidence": observation["detection_confidence"],
                            "ocr_confidence": observation["ocr_confidence"],
                            "watchlist_match": observation["watchlist_match"],
                            "watchlist_label": observation["watchlist_label"],
                            "timestamp": observation["timestamp"].isoformat(),
                        },
                    })

                threat = calculate_threat(
                    tracks,
                    plate_matches=[
                        {"plate_number": track["plate_number"], "priority_score": 20}
                        for track in tracks
                        if track.get("intrusion") and track.get("watchlist_match")
                    ],
                    night_movements=[track for track in night_movements if track.get("intrusion")],
                )

                display = annotate_zones(frame.copy(), zones_for_frame(zones, frame.shape[1], frame.shape[0]))
                for track in tracks:
                    x1, y1, x2, y2 = map(int, track["bbox"])
                    color = (0, 180, 255) if track.get("intrusion") else (80, 210, 120)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(display, f"{track['class']} #{track['track_id']} {track['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2)
                    if track.get("moving"):
                        cv2.putText(display, "MOVING", (x1, min(display.shape[0] - 8, y2 + 36)), cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1)
                    if track.get("plate_number") and track["plate_number"] != "UNKNOWN":
                        cv2.putText(display, f"PLATE {track['plate_number']} {track['plate_confidence']:.0%}", (x1, min(display.shape[0] - 8, y2 + 18)), cv2.FONT_HERSHEY_SIMPLEX, .48, color, 2)

                for observation in plate_observations:
                    px1, py1, px2, py2 = map(int, observation["plate_bbox"])
                    cv2.rectangle(display, (px1, py1), (px2, py2), (255, 190, 60), 1)

                intruder = next((track for track in tracks if track.get("intrusion")), None)
                if intruder and intruder["track_id"] not in alerted_tracks:
                    alerted_tracks.add(intruder["track_id"])
                    zone = intruder["zone_matches"][0]
                    plate_row = observation_rows.get(intruder["track_id"])
                    create_alert(
                        db,
                        camera_id,
                        intruder["track_id"],
                        intruder["class"],
                        intruder["confidence"],
                        zone["name"],
                        threat,
                        display,
                        zone["zone_type"],
                        {
                            "plate_number": intruder.get("plate_number") if intruder.get("plate_number") != "UNKNOWN" else None,
                            "plate_confidence": intruder.get("plate_confidence"),
                            "plate_observation_id": plate_row.id if plate_row else None,
                            "watchlist_match": intruder.get("watchlist_match", False),
                            "watchlist_label": intruder.get("watchlist_label"),
                        },
                        {
                            "scene_condition": scene["scene_condition"] if intruder in night_movements else None,
                            "night_confidence": scene["night_confidence"] if intruder in night_movements else None,
                            "movement_distance": intruder.get("movement_distance") if intruder in night_movements else None,
                        },
                    )
                    state["alerts"] += 1

                cooldown = settings.get("night_alert_cooldown", 30)
                for track in night_movements:
                    if track.get("intrusion"):
                        continue
                    track_key = track["track_id"]
                    if time.monotonic() - night_event_times.get(track_key, 0) < cooldown:
                        continue
                    night_event_times[track_key] = time.monotonic()
                    create_night_movement_event(db, camera_id, track, scene, display)
                    state["night_events"] += 1

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

    @staticmethod
    def _save_anpr_crop(crop, camera_id, track_id, kind, timestamp):
        if crop is None or getattr(crop, "size", 0) == 0:
            return None
        target_dir = PROJECT_ROOT / "data" / "evidence" / "anpr"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"camera_{camera_id}_track_{track_id}_{kind}_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        if not cv2.imwrite(str(target), crop):
            return None
        return f"/evidence/anpr/{target.name}"

    def status(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        if not state:
            return {"camera_id": camera_id, "status": "offline", "frames_processed": 0, "detections": 0, "tracks": 0, "alerts": 0, "scene": {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}, "moving_tracks": 0, "night_events": 0}
        status = state["status"]
        if status == "online" and state["last_frame_at"] and time.monotonic() - state["last_frame_at"] > 20:
            status = "stalled"
        return {"camera_id": camera_id, "status": status, "error": state["error"] or ("No processed frame received recently" if status == "stalled" else None), "frames_processed": state["frames_processed"], "detections": state["detections"], "tracks": len(state["tracks"]), "alerts": state["alerts"], "scene": state["scene"], "moving_tracks": state["moving_tracks"], "night_events": state["night_events"]}

    def latest_frame(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        return state.get("latest") if state else None


stream_manager = StreamManager()
