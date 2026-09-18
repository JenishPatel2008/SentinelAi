from threading import Lock
import os
import json


DEFAULT_RUNTIME_SETTINGS = {
    "detection_confidence": 0.45,
    "vehicle_confidence": 0.45,
    "wildlife_suppression": False,
    "severe_weather_compensation": False,
    "night_vision_filtering": False,
    "anpr_enabled": True,
    "anpr_frame_interval": 5,
    "anpr_min_ocr_confidence": 0.55,
    "night_brightness_threshold": 60,
    "low_light_brightness_threshold": 100,
    "night_confirmation_frames": 5,
    "day_confirmation_frames": 5,
    "movement_threshold": 12,
    "night_alert_cooldown": 30,
    "vehicle_class_confidence_threshold": 0.5,
    "vehicle_class_history_size": 5,
    "vehicle_class_change_confirmation_frames": 3,
    "loitering_time_seconds": 45,
    "loitering_movement_threshold": 80,
    "restricted_zone_dwell_seconds": 10,
    "fence_crossing_count_threshold": 3,
    "fence_crossing_window_seconds": 120,
    "stationary_time_seconds": 60,
    "stationary_movement_threshold": 12,
    "person_vehicle_proximity_threshold": 100,
    "person_vehicle_proximity_seconds": 20,
    "behavior_alert_cooldown_seconds": 30,
    "behavior_track_cleanup_seconds": 180,
    "face_recognition_enabled": False,
    "face_detection_confidence_threshold": 0.5,
    "face_min_size": 24,
    "face_recognition_threshold": 0.363,
    "face_recognition_confirmation_frames": 3,
    "face_recognition_cooldown_seconds": 15,
    "face_sample_interval": 5,
    "face_identity_loss_frames": 5,
    "face_detection_model_path": "ai_models/face/face_detection_yunet_2023mar.onnx",
    "face_recognition_model_path": "ai_models/face/face_recognition_sface_2021dec.onnx",
}

_settings = DEFAULT_RUNTIME_SETTINGS.copy()
_settings_lock = Lock()


def get_runtime_settings():
    with _settings_lock:
        return _settings.copy()


def load_persisted_settings():
    """Load valid runtime overrides after the database schema is available."""
    from ..database.database import SessionLocal
    from ..database.models import RuntimeSetting

    db = SessionLocal()
    try:
        persisted = {}
        for row in db.query(RuntimeSetting).all():
            if row.key not in DEFAULT_RUNTIME_SETTINGS:
                continue
            try:
                persisted[row.key] = json.loads(row.value)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        with _settings_lock:
            _settings.update(persisted)
    finally:
        db.close()


def get_anpr_model_path():
    return os.getenv("PLATE_MODEL_PATH", "ai_models/anpr/plate_model.pt")


def update_runtime_settings(values):
    from ..database.database import SessionLocal
    from ..database.models import RuntimeSetting

    with _settings_lock:
        _settings.update({key: value for key, value in values.items() if value is not None})
        current = _settings.copy()

    db = SessionLocal()
    try:
        for key, value in values.items():
            if key not in DEFAULT_RUNTIME_SETTINGS or value is None:
                continue
            row = db.query(RuntimeSetting).filter(RuntimeSetting.key == key).first()
            if row is None:
                row = RuntimeSetting(key=key, value=json.dumps(value))
                db.add(row)
            else:
                row.value = json.dumps(value)
        db.commit()
    finally:
        db.close()
    return current
