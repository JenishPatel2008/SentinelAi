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


@router.get("", dependencies=[Depends(get_current_operator)])
def read_settings():
    return get_runtime_settings()


@router.patch("", dependencies=[Depends(get_current_operator)])
def write_settings(data: SettingsUpdate):
    return update_runtime_settings(data.model_dump(exclude_none=True))
