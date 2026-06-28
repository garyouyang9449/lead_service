from __future__ import annotations

import os
import uuid
from typing import BinaryIO, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead import Lead, LeadState
from app.schemas.lead import LeadCreate, LeadDetail

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # browsers/curl sometimes send a generic type; accept when extension is valid
    "application/octet-stream",
}


class FileValidationError(Exception):
    """Resume file failed the upload rules (type/size)."""


class LeadNotFound(Exception):
    """No lead exists for the requested id."""


class Storage(Protocol):
    def upload(self, key: str, fileobj: BinaryIO, content_type: str) -> None: ...
    def presigned_url(self, key: str) -> str: ...


def _extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()


def validate_resume(filename: str, content_type: str, size: int) -> None:
    if not filename:
        raise FileValidationError("A resume file is required.")

    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '.{ext}'. Allowed: pdf, doc, docx."
        )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise FileValidationError(f"Unsupported content type '{content_type}'.")

    if size <= 0:
        raise FileValidationError("The resume file is empty.")

    max_bytes = settings.max_resume_mb * 1024 * 1024
    if size > max_bytes:
        raise FileValidationError(
            f"File too large. Maximum size is {settings.max_resume_mb} MB."
        )


def create_lead(
    db: Session,
    storage: Storage,
    data: LeadCreate,
    *,
    filename: str,
    content_type: str,
    fileobj: BinaryIO,
    size: int,
) -> Lead:
    validate_resume(filename, content_type, size)

    lead_id = uuid.uuid4()
    key = f"leads/{lead_id}/{filename}"
    storage.upload(key, fileobj, content_type)

    lead = Lead(
        id=lead_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=str(data.email),
        resume_key=key,
        resume_filename=filename,
        state=LeadState.PENDING,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise LeadNotFound(str(lead_id))
    return lead


def list_leads(db: Session, limit: int = 50, offset: int = 0) -> list[Lead]:
    stmt = (
        select(Lead)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def get_lead_detail(db: Session, storage: Storage, lead_id: uuid.UUID) -> LeadDetail:
    lead = get_lead(db, lead_id)
    url = storage.presigned_url(lead.resume_key)
    return LeadDetail.model_validate({**lead.__dict__, "resume_url": url})
