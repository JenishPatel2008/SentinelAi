from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..core.config import get_runtime_settings, update_runtime_settings
from ..core.security import get_current_operator


router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    detection_confidence: float | None = Field(default=None, ge=0.1, le=0.99)
    vehicle_confidence: float | None = Field(default=None, ge=0.1, le=0.99)
    wildlife_suppression: bool | None = None
    severe_weather_compensation: bool | None = None
    night_vision_filtering: bool | None = None
    anpr_enabled: bool | None = None
    anpr_frame_interval: int | None = Field(default=None, ge=1, le=60)
    anpr_min_ocr_confidence: float | None = Field(default=None, ge=0.1, le=0.99)
    night_brightness_threshold: int | None = Field(default=None, ge=1, le=254)
    low_light_brightness_threshold: int | None = Field(default=None, ge=1, le=254)
    night_confirmation_frames: int | None = Field(default=None, ge=1, le=120)
    day_confirmation_frames: int | None = Field(default=None, ge=1, le=120)
    movement_threshold: float | None = Field(default=None, ge=0, le=1000)
    night_alert_cooldown: int | None = Field(default=None, ge=1, le=3600)
    vehicle_class_confidence_threshold: float | None = Field(default=None, ge=0.1, le=0.99)
    vehicle_class_history_size: int | None = Field(default=None, ge=1, le=30)
    vehicle_class_change_confirmation_frames: int | None = Field(default=None, ge=1, le=30)
    loitering_time_seconds: int | None = Field(default=None, ge=1, le=3600)
    loitering_movement_threshold: float | None = Field(default=None, ge=0, le=10000)
    restricted_zone_dwell_seconds: int | None = Field(default=None, ge=1, le=3600)
    fence_crossing_count_threshold: int | None = Field(default=None, ge=2, le=50)
    fence_crossing_window_seconds: int | None = Field(default=None, ge=1, le=3600)
    stationary_time_seconds: int | None = Field(default=None, ge=1, le=3600)
    stationary_movement_threshold: float | None = Field(default=None, ge=0, le=1000)
    person_vehicle_proximity_threshold: float | None = Field(default=None, ge=1, le=2000)
    person_vehicle_proximity_seconds: int | None = Field(default=None, ge=1, le=3600)
    behavior_alert_cooldown_seconds: int | None = Field(default=None, ge=1, le=3600)
    behavior_track_cleanup_seconds: int | None = Field(default=None, ge=1, le=3600)


@router.get("", dependencies=[Depends(get_current_operator)])
def read_settings():
    return get_runtime_settings()


@router.patch("", dependencies=[Depends(get_current_operator)])
def write_settings(data: SettingsUpdate):
    return update_runtime_settings(data.model_dump(exclude_none=True))
