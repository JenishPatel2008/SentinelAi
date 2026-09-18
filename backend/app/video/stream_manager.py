from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread, current_thread
import json
from queue import Empty, Full, Queue
import time

import cv2

from ..ai.pipeline import DetectionPipeline
from ..ai.anpr import ANPREngine
from ..ai.plate_detector import PlateDetector
from ..ai.night_detector import NightDetector
from ..ai.behavior_engine import BehaviorEngine
from ..ai.face_detector import FaceDetector
from ..ai.face_engine import FaceIntelligence
from ..ai.face_recognition import SFaceEncoder, embedding_from_bytes
from ..ai.threat_engine import calculate_threat
from ..ai.zone_detector import annotate_zones, zones_for_frame
from ..core.config import get_anpr_model_path, get_runtime_settings
from ..database.database import PROJECT_ROOT, SessionLocal
from ..database.models import Camera, Detection, FaceEmbedding, FaceSubject, FaceObservation, PlateObservation, WatchlistEntry, Zone
from ..api.websocket import manager
from ..services.alert_service import create_alert, create_behavior_alert, create_face_event, create_night_movement_event
from ..services.alarm_service import alarm_service
from ..utils.urls import validate_rtsp_url


class StreamManager:
    """Own camera workers and the latest browser-consumable JPEG frame."""

    def __init__(self):
        self.streams = {}
        self.lock = Lock()
        self.starting = set()

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
            if camera.id in self.starting:
                return
            self.starting.add(camera.id)

        try:
            if camera.source_type == "rtsp":
                validate_rtsp_url(source)

            resolved_source = self.resolve_source(source, camera.source_type)
            if isinstance(resolved_source, str) and not resolved_source.startswith(("rtsp://", "http://", "https://")) and not Path(resolved_source).exists():
                raise ValueError("Unable to find the configured video source.")

            if not self.stop(camera.id):
                raise RuntimeError("The previous stream worker is still stopping; try again shortly.")

            state = {"camera_id": camera.id, "status": "starting", "error": None, "source": source, "stop": Event(), "capture": None, "latest": None, "last_frame_at": None, "frame_queue": Queue(maxsize=1), "reader_ready": Event(), "reader_error": None, "source_cycle": 0, "frames_processed": 0, "detections": 0, "tracks": set(), "alerts": 0, "scene": {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}, "moving_tracks": 0, "night_events": 0, "behavior_alerts": 0}
            thread = Thread(target=self._worker, args=(state, resolved_source, camera.source_type), daemon=True, name=f"sentinel-camera-{camera.id}")
            state["thread"] = thread
            with self.lock:
                self.streams[camera.id] = state
            thread.start()
        finally:
            with self.lock:
                self.starting.discard(camera.id)

    def stop(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        if state:
            state["stop"].set()
            if state["status"] in {"starting", "connecting", "online"}:
                state["status"] = "stopping"
            capture = state.get("capture")
            if capture is not None:
                capture.release()
            thread = state.get("thread")
            if thread and thread is not current_thread() and thread.is_alive():
                thread.join(timeout=2)
                return not thread.is_alive()
        return True

    def stop_all(self):
        with self.lock:
            camera_ids = list(self.streams)
        for camera_id in camera_ids:
            self.stop(camera_id)

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
            zones = [{"id": zone.id, "name": zone.name, "zone_type": zone.zone_type, "security_mode": zone.security_mode, "trusted_person_policy": zone.trusted_person_policy, "polygon_points": json.loads(zone.polygon_points), "enabled": zone.enabled} for zone in db.query(Zone).filter(Zone.camera_id == camera_id, Zone.enabled.is_(True)).all()]
            settings = get_runtime_settings()
            vehicle_classes = {"car", "truck", "motorcycle", "bus", "bicycle"}
            pipeline = DetectionPipeline(
                str(PROJECT_ROOT / "ai_models" / "yolo" / "model.pt"),
                min(settings["detection_confidence"], settings["vehicle_confidence"]),
                zones,
                class_confidences={"person": settings["detection_confidence"], **{item: settings["vehicle_confidence"] for item in vehicle_classes}},
                movement_threshold=settings.get("movement_threshold", 12),
                vehicle_class_confidence=settings.get("vehicle_class_confidence_threshold", .5),
                vehicle_class_history_size=settings.get("vehicle_class_history_size", 5),
                vehicle_class_change_confirmation_frames=settings.get("vehicle_class_change_confirmation_frames", 3),
            )
            plate_model_path = Path(get_anpr_model_path())
            if not plate_model_path.is_absolute():
                plate_model_path = PROJECT_ROOT / settings.get("plate_model_path", str(plate_model_path))
            anpr = ANPREngine(
                plate_detector=PlateDetector(
                    plate_model_path,
                    confidence=settings.get("plate_detection_confidence", .35),
                ),
                sample_interval=settings.get("anpr_frame_interval", 5),
                min_confidence=settings.get("anpr_min_ocr_confidence", .55),
            )
            night_detector = NightDetector(
                night_threshold=settings.get("night_brightness_threshold", 60),
                low_light_threshold=settings.get("low_light_brightness_threshold", 100),
                night_confirmation_frames=settings.get("night_confirmation_frames", 5),
                day_confirmation_frames=settings.get("day_confirmation_frames", 5),
            )
            behavior_engine = BehaviorEngine(
                loitering_time_seconds=settings.get("loitering_time_seconds", 45),
                loitering_movement_threshold=settings.get("loitering_movement_threshold", 80),
                restricted_zone_dwell_seconds=settings.get("restricted_zone_dwell_seconds", 10),
                fence_crossing_count_threshold=settings.get("fence_crossing_count_threshold", 3),
                fence_crossing_window_seconds=settings.get("fence_crossing_window_seconds", 120),
                stationary_time_seconds=settings.get("stationary_time_seconds", 60),
                stationary_movement_threshold=settings.get("stationary_movement_threshold", 12),
                proximity_threshold=settings.get("person_vehicle_proximity_threshold", 100),
                proximity_time_seconds=settings.get("person_vehicle_proximity_seconds", 20),
                track_cleanup_seconds=settings.get("behavior_track_cleanup_seconds", 180),
            )
            face_detector = FaceDetector(
                PROJECT_ROOT / settings.get("face_detection_model_path", "ai_models/face/face_detection_yunet_2023mar.onnx"),
                settings.get("face_min_size", 24),
                settings.get("face_detection_confidence_threshold", .5),
            )
            face_encoder = SFaceEncoder(PROJECT_ROOT / settings.get("face_recognition_model_path", "ai_models/face/face_recognition_sface_2021dec.onnx"))
            face_engine = FaceIntelligence(
                face_detector,
                face_encoder,
                enabled=settings.get("face_recognition_enabled", False),
                recognition_threshold=settings.get("face_recognition_threshold", .363),
                confirmation_frames=settings.get("face_recognition_confirmation_frames", 3),
                sample_interval=settings.get("face_sample_interval", 5),
                identity_loss_frames=settings.get("face_identity_loss_frames", 5),
                min_size=settings.get("face_min_size", 24),
                track_cleanup_seconds=settings.get("behavior_track_cleanup_seconds", 180),
            )
            face_subjects = self._load_face_subjects(db)
            watchlist_entries = db.query(WatchlistEntry).filter(WatchlistEntry.enabled.is_(True)).all()
            watchlist = {entry.plate_number: entry for entry in watchlist_entries}
            camera_status = "starting"
            self._set_camera_status(db, camera_id, camera_status)
            alerted_tracks = set()
            movement_alerted_tracks = set()
            face_alarm_tracks = set()
            night_event_times = {}
            behavior_alert_times = {}
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

                if state["source_cycle"] != source_cycle:
                    pipeline.reset()
                    anpr.reset()
                    night_detector.reset()
                    behavior_engine.reset()
                    face_engine.reset()
                    alerted_tracks.clear()
                    movement_alerted_tracks.clear()
                    face_alarm_tracks.clear()
                    night_event_times.clear()
                    behavior_alert_times.clear()
                    source_cycle = state["source_cycle"]

                tracks, threat = pipeline.process(frame)
                state["frames_processed"] += 1
                # Capture readiness is not processing readiness. Keep the camera
                # in starting state until the first frame completes the pipeline.
                if camera_status != "online":
                    camera_status = "online"
                    state["status"] = "online"
                    state["error"] = None
                    self._set_camera_status(db, camera_id, camera_status)
                scene = night_detector.analyze(frame)
                state["scene"] = scene
                for track in tracks:
                    track["scene_condition"] = scene["scene_condition"]
                    track["night_confidence"] = scene["night_confidence"]
                night_movements = [track for track in tracks if scene["scene_condition"] in {"NIGHT", "LOW_LIGHT"} and track.get("moving")]
                state["moving_tracks"] = len([track for track in tracks if track.get("moving")])
                tracks, plate_observations = anpr.observe(
                    frame,
                    tracks,
                    camera_id,
                    frame_index=state["frames_processed"],
                    timestamp=datetime.utcnow(),
                    watchlist=watchlist,
                ) if settings.get("anpr_enabled", True) else (tracks, [])
                tracks, behavior_observations = behavior_engine.update(tracks, scene, timestamp=datetime.utcnow())
                tracks, face_observations, face_events = face_engine.update(frame, tracks, face_subjects, timestamp=datetime.utcnow())
                for track in tracks:
                    protected_zones = [zone for zone in track.get("zone_matches", []) if zone.get("security_mode") == "PROTECTED" or zone.get("trusted_person_policy") == "ONLY_TRUSTED"]
                    track["protected_zone"] = bool(protected_zones)
                    if protected_zones and track.get("class") == "person":
                        track["intrusion"] = track.get("identity_status") != "trusted"
                visible_track_ids = {track["track_id"] for track in tracks}
                movement_alerted_tracks.intersection_update(visible_track_ids)
                face_alarm_tracks.intersection_update(visible_track_ids)
                if state["frames_processed"] % 15 == 0:
                    manager.broadcast_from_sync({
                        "type": "scene",
                        "data": {"camera_id": camera_id, **scene, "moving_tracks": state["moving_tracks"], "tracks": [{"track_id": track["track_id"], "object_type": track["class"], "vehicle_class": track.get("vehicle_class"), "vehicle_class_confidence": track.get("vehicle_class_confidence"), "moving": track.get("moving", False), "behavior_state": track.get("behavior_state", "NORMAL"), "behavior_types": track.get("behavior_types", []), "dwell_seconds": track.get("dwell_seconds", 0), "stationary_seconds": track.get("stationary_seconds", 0), "face_status": track.get("face_status"), "identity_status": track.get("identity_status"), "subject_id": track.get("subject_id"), "subject_label": track.get("subject_label"), "subject_category": track.get("subject_category"), "face_confidence": track.get("face_confidence"), "face_similarity": track.get("face_similarity"), "protected_zone": track.get("protected_zone", False), "intrusion": track.get("intrusion", False)} for track in tracks], "timestamp": datetime.utcnow().isoformat()},
                    })
                state["detections"] += len(tracks)
                state["tracks"].update(track["track_id"] for track in tracks)
                now = datetime.utcnow()
                for track in tracks:
                    db.add(Detection(camera_id=camera_id, track_id=track["track_id"], class_id=track.get("class_id"), object_type=track["class"], confidence=track["confidence"], category=track.get("category"), vehicle_class=track.get("vehicle_class"), vehicle_class_confidence=track.get("vehicle_class_confidence"), timestamp=now))

                for observation in face_observations:
                    db.add(FaceObservation(camera_id=camera_id, track_id=observation["track_id"], subject_id=observation.get("subject_id"), timestamp=observation["timestamp"], face_status=observation["face_status"], recognition_status=observation["recognition_status"], identity_status=observation["identity_status"], face_confidence=observation.get("face_confidence"), similarity=observation.get("similarity"), face_bbox=json.dumps(observation.get("face_bbox")) if observation.get("face_bbox") else None))

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
                    behaviors=behavior_observations,
                    identity_context=tracks,
                )

                display = annotate_zones(frame.copy(), zones_for_frame(zones, frame.shape[1], frame.shape[0]))
                for track in tracks:
                    x1, y1, x2, y2 = map(int, track["bbox"])
                    color = (0, 180, 255) if track.get("intrusion") else (80, 210, 120)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    label = track.get("vehicle_class") if track.get("category") == "vehicle" else track["class"]
                    cv2.putText(display, f"{label} #{track['track_id']} {track['confidence']:.2f}", (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2)
                    if track.get("moving"):
                        cv2.putText(display, "MOVING", (x1, min(display.shape[0] - 8, y2 + 36)), cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1)
                    if track.get("behavior_types"):
                        cv2.putText(display, track["behavior_types"][0].replace("_", " "), (x1, min(display.shape[0] - 8, y2 + 52)), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 80, 255), 1)
                    if track.get("face_bbox"):
                        fx1, fy1, fx2, fy2 = map(int, track["face_bbox"])
                        cv2.rectangle(display, (fx1, fy1), (fx2, fy2), (255, 210, 70), 1)
                    identity_label = track.get("subject_label") if track.get("identity_status") == "trusted" else track.get("identity_status", "unverified").upper()
                    if track.get("class") == "person":
                        cv2.putText(display, identity_label, (x1, min(display.shape[0] - 8, y2 + 68)), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 210, 70), 1)
                    if track.get("plate_number") and track["plate_number"] != "UNKNOWN":
                        cv2.putText(display, f"PLATE {track['plate_number']} {track['plate_confidence']:.0%}", (x1, min(display.shape[0] - 8, y2 + 18)), cv2.FONT_HERSHEY_SIMPLEX, .48, color, 2)

                for observation in plate_observations:
                    px1, py1, px2, py2 = map(int, observation["plate_bbox"])
                    cv2.rectangle(display, (px1, py1), (px2, py2), (255, 190, 60), 1)

                for face_event in face_events:
                    create_face_event(db, camera_id, face_event, display)

                # Emit one alert when a tracked object starts moving. The track
                # set prevents a database/WebSocket storm on every frame.
                for moving_track in tracks:
                    if not moving_track.get("moving"):
                        continue
                    track_id = moving_track["track_id"]
                    if track_id in movement_alerted_tracks:
                        continue
                    movement_alerted_tracks.add(track_id)
                    zone = moving_track.get("zone_matches", [{}])[0]
                    movement_threat = {
                        "score": 30,
                        "severity": "MEDIUM",
                        "reason": f"Movement detected: {moving_track['class'].title()} track #{track_id} moved {moving_track.get('movement_distance', 0)} pixels",
                    }
                    create_alert(
                        db,
                        camera_id,
                        track_id,
                        moving_track["class"],
                        moving_track["confidence"],
                        zone.get("name") or "Open area",
                        movement_threat,
                        display,
                        zone.get("zone_type"),
                        night_info={"movement_distance": moving_track.get("movement_distance")},
                        identity_info={
                            "identity_status": moving_track.get("identity_status"),
                            "subject_id": moving_track.get("subject_id"),
                            "subject_label": moving_track.get("subject_label"),
                            "subject_category": moving_track.get("subject_category"),
                            "face_status": moving_track.get("face_status"),
                            "face_confidence": moving_track.get("face_confidence"),
                            "face_similarity": moving_track.get("face_similarity"),
                            "face_bbox": moving_track.get("face_bbox"),
                        },
                        event_type="movement_detected",
                    )

                # An unknown face or an obstructed face is an immediate operator
                # alarm unless the existing protected-zone path handles it.
                for person in tracks:
                    if person.get("class") != "person" or person.get("protected_zone"):
                        continue
                    face_alarm_reason = None
                    face_event_type = None
                    if person.get("identity_status") == "unknown" and person.get("face_status") == "detected":
                        face_alarm_reason = "Unknown face detected"
                        face_event_type = "unknown_face_detected"
                    elif person.get("face_status") in {"obstructed", "unavailable"}:
                        face_alarm_reason = "Possible face covering or obstructed face detected"
                        face_event_type = "possible_face_covering"
                    if not face_alarm_reason or person["track_id"] in face_alarm_tracks:
                        continue
                    face_alarm_tracks.add(person["track_id"])
                    zone = person.get("zone_matches", [{}])[0]
                    face_threat = {"score": 80, "severity": "HIGH", "reason": face_alarm_reason}
                    alert = create_alert(
                        db,
                        camera_id,
                        person["track_id"],
                        "person",
                        person["confidence"],
                        zone.get("name") or "Open area",
                        face_threat,
                        display,
                        zone.get("zone_type"),
                        identity_info={
                            "identity_status": person.get("identity_status"),
                            "subject_id": person.get("subject_id"),
                            "subject_label": person.get("subject_label"),
                            "subject_category": person.get("subject_category"),
                            "face_status": person.get("face_status"),
                            "face_confidence": person.get("face_confidence"),
                            "face_similarity": person.get("face_similarity"),
                            "face_bbox": person.get("face_bbox"),
                            "protected_zone": False,
                            "alarm_trigger": True,
                        },
                        event_type=face_event_type,
                    )
                    alarm_service.trigger_alarm(camera_id, alert.id, person["track_id"], zone.get("name") or "Open area", face_alarm_reason)

                intruder = next((track for track in tracks if track.get("intrusion")), None)
                if intruder:
                    zone = intruder["zone_matches"][0]
                    alert_key = (intruder["track_id"], zone.get("id"))
                    if alert_key not in alerted_tracks:
                        alerted_tracks.add(alert_key)
                        plate_row = observation_rows.get(intruder["track_id"])
                        alert = create_alert(
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
                        {
                            "vehicle_class": intruder.get("vehicle_class"),
                            "vehicle_class_confidence": intruder.get("vehicle_class_confidence"),
                        },
                            next((item for item in behavior_observations if item.get("track_id") == intruder["track_id"]), None),
                            identity_info={
                                "identity_status": intruder.get("identity_status"), "subject_id": intruder.get("subject_id"), "subject_label": intruder.get("subject_label"), "subject_category": intruder.get("subject_category"), "face_status": intruder.get("face_status"), "face_confidence": intruder.get("face_confidence"), "face_similarity": intruder.get("face_similarity"), "face_bbox": intruder.get("face_bbox"), "protected_zone": intruder.get("protected_zone", False),
                            },
                            event_type="unverified_person_in_protected_zone" if intruder.get("protected_zone") else None,
                        )
                        state["alerts"] += 1
                        if intruder.get("protected_zone"):
                            alarm_service.trigger_alarm(camera_id, alert.id, intruder["track_id"], zone["name"], threat["reason"])

                cooldown = settings.get("behavior_alert_cooldown_seconds", 30)
                for behavior in behavior_observations:
                    track = next((item for item in tracks if item.get("track_id") == behavior.get("track_id")), {})
                    if track.get("intrusion"):
                        # The intrusion alert already stores the behavior context for this frame.
                        continue
                    behavior_key = (behavior.get("track_id"), behavior.get("behavior_type"))
                    current_time = time.monotonic()
                    if current_time - behavior_alert_times.get(behavior_key, 0) < cooldown:
                        continue
                    behavior_alert_times[behavior_key] = current_time
                    behavior_threat = calculate_threat([], behaviors=[behavior])
                    create_behavior_alert(db, camera_id, track, behavior, behavior_threat, display)
                    state["behavior_alerts"] += 1

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
            state["capture"] = capture
            if not capture.isOpened():
                capture.release()
                state["capture"] = None
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
                state["capture"] = None

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
    def _load_face_subjects(db):
        subjects = []
        for subject, embedding in db.query(FaceSubject, FaceEmbedding).join(FaceEmbedding, FaceEmbedding.subject_id == FaceSubject.id).filter(FaceSubject.enabled.is_(True)).all():
            try:
                vector = embedding_from_bytes(embedding.embedding, embedding.dimension)
                if vector.size == embedding.dimension:
                    subjects.append({"id": subject.id, "label": subject.label, "category": subject.category, "enabled": subject.enabled, "embedding": vector})
            except (TypeError, ValueError):
                continue
        return subjects

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
            return {"camera_id": camera_id, "status": "offline", "frames_processed": 0, "detections": 0, "tracks": 0, "alerts": 0, "scene": {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}, "moving_tracks": 0, "night_events": 0, "behavior_alerts": 0}
        status = state["status"]
        if status == "online" and state["last_frame_at"] and time.monotonic() - state["last_frame_at"] > 20:
            status = "stalled"
        return {"camera_id": camera_id, "status": status, "error": state["error"] or ("No processed frame received recently" if status == "stalled" else None), "frames_processed": state["frames_processed"], "detections": state["detections"], "tracks": len(state["tracks"]), "alerts": state["alerts"], "scene": state["scene"], "moving_tracks": state["moving_tracks"], "night_events": state["night_events"], "behavior_alerts": state.get("behavior_alerts", 0)}

    def latest_frame(self, camera_id):
        with self.lock:
            state = self.streams.get(camera_id)
        return state.get("latest") if state else None


stream_manager = StreamManager()
