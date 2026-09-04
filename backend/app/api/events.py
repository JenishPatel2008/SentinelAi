from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import Event
from ..database.schemas import EventResponse

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("", response_model=list[EventResponse])
def list_events(db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.timestamp.desc()).limit(200).all()
