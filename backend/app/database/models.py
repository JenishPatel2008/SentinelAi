from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
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

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )


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


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(30), nullable=False)
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
