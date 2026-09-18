from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IncidentResponse(BaseModel):
    id: int
    incident_code: str
    alert_id: int
    camera_id: int
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentUpdate(BaseModel):
    status: str
