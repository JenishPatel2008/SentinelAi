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
    source_type: str = "video"
    status: str = "offline"


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    camera_code: str | None = None
    name: str | None = None
    sector: str | None = None
    stream_url: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    is_active: bool | None = None
    source_type: str | None = None
    status: str | None = None


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
    camera_id: int | None = None
    track_id: int | None = None
    object_type: str | None = None
    zone: str | None = None
    score: int | None = None
    reason: str | None = None
    evidence_path: str | None = None
    timestamp: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


class StreamRequest(BaseModel):
    camera_id: int


class AnalyticsResponse(BaseModel):
    total_detections: int
    active_alerts: int
    critical_alerts: int
    total_events: int
