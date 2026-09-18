from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    LargeBinary,
)

from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    camera_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    sector: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    stream_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    location_lat: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    location_lng: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(String(20), default="video", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="offline", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id"),
        nullable=False,
        index=True,
    )

    object_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    track_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    category: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    vehicle_class: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    vehicle_class_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class PlateObservation(Base):
    __tablename__ = "plate_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    plate_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    plate_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    original_crop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    processed_crop_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    watchlist_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class WatchlistEntry(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FaceSubject(Base):
    __tablename__ = "face_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="authorized", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("face_subjects.id"), unique=True, nullable=False, index=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String(30), default="cosine_similarity", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class FaceObservation(Base):
    __tablename__ = "face_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False, index=True)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("face_subjects.id"), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    face_status: Mapped[str] = mapped_column(String(30), nullable=False)
    recognition_status: Mapped[str] = mapped_column(String(30), nullable=False)
    identity_status: Mapped[str] = mapped_column(String(30), nullable=False)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    plate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    watchlist_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zone_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scene_condition: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    night_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    movement_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vehicle_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vehicle_class_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    behavior_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    behavior_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    behavior_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    subject_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subject_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    face_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(30), nullable=False)
    security_mode: Mapped[str] = mapped_column(String(20), default="MONITORED", nullable=False)
    trusted_person_policy: Mapped[str] = mapped_column(String(40), default="NO_SPECIAL_POLICY", nullable=False)
    polygon_points: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    camera_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zone_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    plate_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    plate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    plate_observation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watchlist_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    watchlist_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scene_condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    night_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    movement_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    vehicle_class_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    behavior_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    behavior_state: Mapped[str | None] = mapped_column(String(30), nullable=True)
    behavior_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    identity_status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    subject_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    subject_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subject_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    face_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_bbox: Mapped[str | None] = mapped_column(Text, nullable=True)
    alarm_status: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incident_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    camera_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
