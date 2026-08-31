from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    camera_code: str
    name: str
    sector: str
    stream_url: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class DetectionResponse(BaseModel):
    id: int
    camera_id: int
    object_type: str
    confidence: float
    track_id: int | None
    timestamp: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class EventResponse(BaseModel):
    id: int
    camera_id: int
    event_type: str
    severity: str
    description: str | None
    timestamp: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class AlertResponse(BaseModel):
    id: int
    event_id: int
    severity: str
    status: str
    message: str
    created_at: datetime
    acknowledged_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True
    )