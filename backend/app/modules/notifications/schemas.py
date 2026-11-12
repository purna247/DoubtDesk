from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    institution_id: uuid.UUID
    user_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    notification_type: str = Field(..., max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    target_type: Optional[str] = None
    target_id: Optional[str] = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    user_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID] = None
    notification_type: str
    title: str
    message: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread_count: int

