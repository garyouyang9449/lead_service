from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.lead import LeadState


class LeadCreate(BaseModel):
    """Validated prospect-supplied metadata (file handled separately)."""

    first_name: str
    last_name: str
    email: EmailStr


class LeadStateUpdate(BaseModel):
    """Attorney-driven state change."""

    state: LeadState


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    resume_filename: str
    state: LeadState
    created_at: datetime
    updated_at: datetime


class LeadDetail(LeadRead):
    resume_url: str
