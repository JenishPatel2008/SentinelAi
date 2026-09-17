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
