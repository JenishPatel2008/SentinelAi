from threading import Lock
import os


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
}

_settings = DEFAULT_RUNTIME_SETTINGS.copy()
_settings_lock = Lock()


def get_runtime_settings():
    with _settings_lock:
        return _settings.copy()


def get_anpr_model_path():
    return os.getenv("PLATE_MODEL_PATH", "ai_models/anpr/plate_model.pt")


def update_runtime_settings(values):
    with _settings_lock:
        _settings.update({key: value for key, value in values.items() if value is not None})
        return _settings.copy()
