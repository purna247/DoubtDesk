from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    event_code: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    payload_json: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


class AuditQueryResponse(BaseModel):
    events: List[AuditEventOut]
    total_count: int

