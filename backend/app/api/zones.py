import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import Camera, Zone
from ..database.schemas import ZoneCreate, ZoneResponse, ZoneUpdate

router = APIRouter(tags=["Zones"])

def as_response(zone):
    return {
        "id": zone.id,
        "camera_id": zone.camera_id,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "polygon_points": json.loads(zone.polygon_points),
        "enabled": zone.enabled,
        "created_at": zone.created_at,
        "updated_at": zone.updated_at,
    }

@router.get("/api/cameras/{camera_id}/zones", response_model=list[ZoneResponse])
def list_zones(camera_id: int, db: Session = Depends(get_db)):
    if db.get(Camera, camera_id) is None:
        raise HTTPException(404, "Camera not found")
    return [as_response(zone) for zone in db.query(Zone).filter(Zone.camera_id == camera_id).order_by(Zone.id).all()]

@router.post("/api/cameras/{camera_id}/zones", response_model=ZoneResponse, status_code=201)
def create_zone(camera_id: int, data: ZoneCreate, db: Session = Depends(get_db)):
    if db.get(Camera, camera_id) is None:
        raise HTTPException(404, "Camera not found")
    zone = Zone(camera_id=camera_id, name=data.name, zone_type=data.zone_type, polygon_points=json.dumps(data.polygon_points), enabled=data.enabled)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return as_response(zone)

@router.get("/api/zones/{zone_id}", response_model=ZoneResponse)
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(404, "Zone not found")
    return as_response(zone)

@router.put("/api/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(zone_id: int, data: ZoneUpdate, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(404, "Zone not found")
    values = data.model_dump(exclude_unset=True)
    if "polygon_points" in values:
        values["polygon_points"] = json.dumps(values["polygon_points"])
    for key, value in values.items():
        setattr(zone, key, value)
    db.commit()
    db.refresh(zone)
    return as_response(zone)

@router.delete("/api/zones/{zone_id}")
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(404, "Zone not found")
    db.delete(zone)
    db.commit()
    return {"zone_id": zone_id, "status": "deleted"}

@router.patch("/api/zones/{zone_id}/enabled", response_model=ZoneResponse)
def set_zone_enabled(zone_id: int, enabled: bool, db: Session = Depends(get_db)):
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(404, "Zone not found")
    zone.enabled = enabled
    db.commit()
    db.refresh(zone)
    return as_response(zone)
