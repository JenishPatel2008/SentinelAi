from threading import Lock


DEFAULT_RUNTIME_SETTINGS = {
    "detection_confidence": 0.45,
    "vehicle_confidence": 0.45,
    "wildlife_suppression": False,
    "severe_weather_compensation": False,
    "night_vision_filtering": False,
}

_settings = DEFAULT_RUNTIME_SETTINGS.copy()
_settings_lock = Lock()


def get_runtime_settings():
    with _settings_lock:
        return _settings.copy()


def update_runtime_settings(values):
    with _settings_lock:
        _settings.update({key: value for key, value in values.items() if value is not None})
        return _settings.copy()
