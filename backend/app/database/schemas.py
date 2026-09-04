from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    zone_type: str | None = None
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


ZONE_TYPES = {"restricted", "high_security", "vehicle_restricted", "monitoring"}

class ZoneBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    zone_type: str
    polygon_points: list[dict[str, float]] = Field(min_length=3)
    enabled: bool = True

    @field_validator("zone_type")
    @classmethod
    def supported_zone_type(cls, value):
        if value not in ZONE_TYPES:
            raise ValueError(f"Unsupported zone type: {value}")
        return value

    @field_validator("polygon_points")
    @classmethod
    def normalized_points(cls, points):
        for point in points:
            if set(point) != {"x", "y"} or not (0 <= point["x"] <= 1 and 0 <= point["y"] <= 1):
                raise ValueError("Polygon points must contain normalized x/y values between 0 and 1")
        return points

class ZoneCreate(ZoneBase):
    pass

class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    zone_type: str | None = None
    polygon_points: list[dict[str, float]] | None = Field(default=None, min_length=3)
    enabled: bool | None = None

    @field_validator("zone_type")
    @classmethod
    def supported_update_type(cls, value):
        if value is not None and value not in ZONE_TYPES:
            raise ValueError(f"Unsupported zone type: {value}")
        return value

    @field_validator("polygon_points")
    @classmethod
    def normalized_update_points(cls, points):
        if points is not None:
            for point in points:
                if set(point) != {"x", "y"} or not (0 <= point["x"] <= 1 and 0 <= point["y"] <= 1):
                    raise ValueError("Polygon points must contain normalized x/y values between 0 and 1")
        return points

class ZoneResponse(ZoneBase):
    id: int
    camera_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
