import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..ai.ocr import normalize_plate_text
from ..database.database import get_db
from ..database.models import Camera, PlateObservation, WatchlistEntry
from ..database.schemas import PlateObservationResponse, WatchlistCreate, WatchlistResponse, WatchlistUpdate


router = APIRouter(prefix="/api", tags=["ANPR"])


def observation_response(item, camera=None, watchlist=None):
    return {
        "id": item.id,
        "camera_id": item.camera_id,
        "camera_code": camera.camera_code if camera else None,
        "camera_name": camera.name if camera else None,
        "track_id": item.track_id,
        "vehicle_type": item.vehicle_type,
        "vehicle_confidence": item.vehicle_confidence,
        "plate_bbox": json.loads(item.plate_bbox) if item.plate_bbox else None,
        "plate_number": item.plate_number,
        "plate_confidence": item.plate_confidence,
        "detection_confidence": item.detection_confidence,
        "ocr_confidence": item.ocr_confidence,
        "original_crop_path": item.original_crop_path,
        "processed_crop_path": item.processed_crop_path,
        "watchlist_id": item.watchlist_id,
        "watchlist_label": watchlist.label if watchlist else None,
        "timestamp": item.timestamp,
    }


@router.get("/plates/history", response_model=list[PlateObservationResponse])
def plate_history(
    plate: str | None = Query(default=None),
    camera_id: int | None = Query(default=None),
    vehicle_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(PlateObservation)
    if plate:
        query = query.filter(PlateObservation.plate_number.like(f"%{normalize_plate_text(plate)}%"))
    if camera_id is not None:
        query = query.filter(PlateObservation.camera_id == camera_id)
    if vehicle_type:
        query = query.filter(PlateObservation.vehicle_type == vehicle_type)
    rows = query.order_by(PlateObservation.timestamp.desc()).limit(limit).all()
    camera_ids = {row.camera_id for row in rows}
    watchlist_ids = {row.watchlist_id for row in rows if row.watchlist_id}
    cameras = {camera.id: camera for camera in db.query(Camera).filter(Camera.id.in_(camera_ids)).all()} if camera_ids else {}
    watchlist = {entry.id: entry for entry in db.query(WatchlistEntry).filter(WatchlistEntry.id.in_(watchlist_ids)).all()} if watchlist_ids else {}
    return [observation_response(row, cameras.get(row.camera_id), watchlist.get(row.watchlist_id)) for row in rows]


@router.get("/watchlist", response_model=list[WatchlistResponse])
def list_watchlist(db: Session = Depends(get_db)):
    return db.query(WatchlistEntry).order_by(WatchlistEntry.created_at.desc()).all()


@router.post("/watchlist", response_model=WatchlistResponse, status_code=201)
def create_watchlist_entry(data: WatchlistCreate, db: Session = Depends(get_db)):
    entry = WatchlistEntry(**data.model_dump())
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Plate is already on the watchlist") from error
    db.refresh(entry)
    return entry


@router.put("/watchlist/{entry_id}", response_model=WatchlistResponse)
def update_watchlist_entry(entry_id: int, data: WatchlistUpdate, db: Session = Depends(get_db)):
    entry = db.get(WatchlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Plate is already on the watchlist") from error
    db.refresh(entry)
    return entry


@router.delete("/watchlist/{entry_id}")
def delete_watchlist_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(WatchlistEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    db.delete(entry)
    db.commit()
    return {"entry_id": entry_id, "status": "deleted"}
