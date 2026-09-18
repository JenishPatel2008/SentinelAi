from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from ..utils.urls import sanitize_stream_url, validate_rtsp_url


class CameraBase(BaseModel):
    camera_code: str
    name: str
    sector: str
    stream_url: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    is_active: bool = True
    source_type: str = "mp4"
    status: str = "offline"

    @field_validator("source_type", mode="before")
    @classmethod
    def supported_source_type(cls, value):
        value = str(value or "").strip().lower()
        if value not in {"video", "mp4", "rtsp", "webcam"}:
            raise ValueError("Source type must be mp4, rtsp, or webcam")
        return value

    @model_validator(mode="after")
    def validate_source(self):
        if self.stream_url and self.stream_url.strip().lower().startswith("rtsp://") and self.source_type != "rtsp":
            raise ValueError("An RTSP URL requires source_type='rtsp'")
        if self.source_type == "rtsp":
            validate_rtsp_url(self.stream_url)
        return self


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

    @field_validator("source_type", mode="before")
    @classmethod
    def supported_update_source_type(cls, value):
        if value is None:
            return value
        value = str(value).strip().lower()
        if value not in {"video", "mp4", "rtsp", "webcam"}:
            raise ValueError("Source type must be mp4, rtsp, or webcam")
        return value

    @field_validator("stream_url")
    @classmethod
    def validate_rtsp_stream_url(cls, value):
        if value and value.strip().lower().startswith("rtsp://"):
            return validate_rtsp_url(value)
        return value


class RtspTestRequest(BaseModel):
    stream_url: str

    @field_validator("stream_url")
    @classmethod
    def valid_rtsp_url(cls, value):
        return validate_rtsp_url(value)


class CameraResponse(CameraBase):
    id: int
    created_at: datetime

    @field_serializer("stream_url")
    def hide_stream_credentials(self, value):
        return sanitize_stream_url(value) if self.source_type == "rtsp" else value

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


class PlateObservationResponse(BaseModel):
    id: int
    camera_id: int
    camera_code: str | None = None
    camera_name: str | None = None
    track_id: int
    vehicle_type: str
    vehicle_confidence: float
    plate_bbox: list[float] | None = None
    plate_number: str
    plate_confidence: float
    detection_confidence: float
    ocr_confidence: float
    original_crop_path: str | None = None
    processed_crop_path: str | None = None
    watchlist_id: int | None = None
    watchlist_label: str | None = None
    timestamp: datetime
    class_id: int | None = None
    category: str | None = None
    vehicle_class: str | None = None
    vehicle_class_confidence: float | None = None


class WatchlistBase(BaseModel):
    plate_number: str = Field(min_length=6, max_length=20)
    label: str = Field(min_length=1, max_length=100)
    priority: str = Field(default="HIGH", min_length=1, max_length=20)
    notes: str | None = None
    enabled: bool = True

    @field_validator("plate_number")
    @classmethod
    def normalized_watchlist_plate(cls, value):
        from ..ai.ocr import is_plausible_plate, normalize_plate_text

        normalized = normalize_plate_text(value)
        if not is_plausible_plate(normalized):
            raise ValueError("Plate number must use a supported registration format")
        return normalized

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value):
        value = value.upper()
        if value not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("Priority must be LOW, MEDIUM, HIGH, or CRITICAL")
        return value


class WatchlistCreate(WatchlistBase):
    pass


class WatchlistUpdate(BaseModel):
    plate_number: str | None = Field(default=None, min_length=6, max_length=20)
    label: str | None = Field(default=None, min_length=1, max_length=100)
    priority: str | None = Field(default=None, min_length=1, max_length=20)
    notes: str | None = None
    enabled: bool | None = None

    @field_validator("plate_number")
    @classmethod
    def normalized_update_plate(cls, value):
        if value is None:
            return value
        from ..ai.ocr import is_plausible_plate, normalize_plate_text

        normalized = normalize_plate_text(value)
        if not is_plausible_plate(normalized):
            raise ValueError("Plate number must use a supported registration format")
        return normalized

    @field_validator("priority")
    @classmethod
    def valid_update_priority(cls, value):
        if value is None:
            return value
        value = value.upper()
        if value not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("Priority must be LOW, MEDIUM, HIGH, or CRITICAL")
        return value


class WatchlistResponse(WatchlistBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaceSubjectResponse(BaseModel):
    id: int
    label: str
    category: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FaceSubjectUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    enabled: bool | None = None


class FaceObservationResponse(BaseModel):
    id: int
    camera_id: int
    track_id: int
    subject_id: int | None = None
    timestamp: datetime
    face_status: str
    recognition_status: str
    identity_status: str
    face_confidence: float | None = None
    similarity: float | None = None
    face_bbox: str | None = None
    evidence_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EventResponse(BaseModel):
    id: int
    camera_id: int
    event_type: str
    severity: str
    description: str | None
    timestamp: datetime
    plate_number: str | None = None
    plate_confidence: float | None = None
    watchlist_match: bool = False
    track_id: int | None = None
    object_type: str | None = None
    zone: str | None = None
    zone_type: str | None = None
    scene_condition: str | None = None
    night_confidence: float | None = None
    movement_distance: float | None = None
    duration_seconds: float | None = None
    evidence_path: str | None = None
    vehicle_class: str | None = None
    vehicle_class_confidence: float | None = None
    behavior_type: str | None = None
    behavior_state: str | None = None
    behavior_reason: str | None = None
    behavior_metadata: str | None = None
    identity_status: str | None = None
    subject_id: int | None = None
    subject_label: str | None = None
    subject_category: str | None = None
    face_status: str | None = None
    face_confidence: float | None = None
    face_similarity: float | None = None
    face_bbox: str | None = None

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
    plate_number: str | None = None
    plate_confidence: float | None = None
    plate_observation_id: int | None = None
    watchlist_match: bool = False
    watchlist_label: str | None = None
    scene_condition: str | None = None
    night_confidence: float | None = None
    movement_distance: float | None = None
    vehicle_class: str | None = None
    vehicle_class_confidence: float | None = None
    behavior_type: str | None = None
    behavior_state: str | None = None
    behavior_reason: str | None = None
    behavior_metadata: str | None = None
    behavior_duration_seconds: float | None = None
    identity_status: str | None = None
    subject_id: int | None = None
    subject_label: str | None = None
    subject_category: str | None = None
    face_status: str | None = None
    face_confidence: float | None = None
    face_similarity: float | None = None
    face_bbox: str | None = None
    alarm_status: str | None = None

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
    night_movements: int = 0
    night_intrusions: int = 0
    night_vehicle_movements: int = 0
    total_vehicles: int = 0
    cars: int = 0
    motorcycles: int = 0
    buses: int = 0
    trucks: int = 0
    bicycles: int = 0
    unknown_vehicles: int = 0
    suspicious_activities: int = 0
    loitering: int = 0
    repeated_fence_crossings: int = 0
    extended_restricted_presence: int = 0
    prolonged_stationary: int = 0
    person_vehicle_proximity: int = 0
    night_suspicious_events: int = 0
    faces_detected: int = 0
    known_faces: int = 0
    unknown_faces: int = 0
    face_watchlist_matches: int = 0


ZONE_TYPES = {"restricted", "high_security", "vehicle_restricted", "monitoring"}

class ZoneBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    zone_type: str
    security_mode: str = "MONITORED"
    trusted_person_policy: str = "NO_SPECIAL_POLICY"
    polygon_points: list[dict[str, float]] = Field(min_length=3)
    enabled: bool = True

    @field_validator("zone_type")
    @classmethod
    def supported_zone_type(cls, value):
        if value not in ZONE_TYPES:
            raise ValueError(f"Unsupported zone type: {value}")
        return value

    @field_validator("security_mode")
    @classmethod
    def supported_security_mode(cls, value):
        value = value.upper()
        if value not in {"OPEN", "MONITORED", "PROTECTED"}:
            raise ValueError("Security mode must be OPEN, MONITORED, or PROTECTED")
        return value

    @field_validator("trusted_person_policy")
    @classmethod
    def supported_trusted_person_policy(cls, value):
        value = value.upper()
        if value not in {"NO_SPECIAL_POLICY", "ONLY_TRUSTED"}:
            raise ValueError("Trusted-person policy must be NO_SPECIAL_POLICY or ONLY_TRUSTED")
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
    security_mode: str | None = None
    trusted_person_policy: str | None = None
    polygon_points: list[dict[str, float]] | None = Field(default=None, min_length=3)
    enabled: bool | None = None

    @field_validator("zone_type")
    @classmethod
    def supported_update_type(cls, value):
        if value is not None and value not in ZONE_TYPES:
            raise ValueError(f"Unsupported zone type: {value}")
        return value

    @field_validator("security_mode")
    @classmethod
    def supported_update_security_mode(cls, value):
        if value is not None and value.upper() not in {"OPEN", "MONITORED", "PROTECTED"}:
            raise ValueError("Security mode must be OPEN, MONITORED, or PROTECTED")
        return value.upper() if value is not None else value

    @field_validator("trusted_person_policy")
    @classmethod
    def supported_update_policy(cls, value):
        if value is not None and value.upper() not in {"NO_SPECIAL_POLICY", "ONLY_TRUSTED"}:
            raise ValueError("Trusted-person policy must be NO_SPECIAL_POLICY or ONLY_TRUSTED")
        return value.upper() if value is not None else value

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
