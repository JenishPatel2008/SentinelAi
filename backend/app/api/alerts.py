from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..database.models import Alert
from ..database.schemas import AlertResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


class AlertDecision(BaseModel):
    decision: Literal["confirmed", "declined"]

@router.get("", response_model=list[AlertResponse])
def list_alerts(status_filter: Literal["active", "confirmed", "declined", "all"] = Query("active", alias="status"), db: Session = Depends(get_db)):
    query = db.query(Alert)
    if status_filter != "all":
        query = query.filter(Alert.status == status_filter)
    return query.order_by(Alert.created_at.desc()).limit(200).all()

@router.get("/{alert_id}", response_model=AlertResponse)
def read_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}/decision", response_model=AlertResponse)
def decide_alert(alert_id: int, decision: AlertDecision, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = decision.decision
    alert.acknowledged_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return alert
