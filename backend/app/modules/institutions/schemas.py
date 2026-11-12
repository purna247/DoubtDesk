from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class InstitutionCreate(BaseModel):
    institution_code: str = Field(..., min_length=2, max_length=40)
    legal_name: str = Field(..., min_length=2)
    display_name: str = Field(..., min_length=2)
    primary_domain: Optional[str] = None
    timezone: str = "Asia/Kolkata"


class InstitutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_code: str
    legal_name: str
    display_name: str
    primary_domain: Optional[str] = None
    status: str
    timezone: str
    created_at: datetime

