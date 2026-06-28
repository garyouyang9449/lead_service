from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_storage
from app.schemas.lead import LeadCreate, LeadDetail, LeadRead, LeadStateUpdate
from app.services.leads import (
    FileValidationError,
    InvalidStateTransition,
    LeadNotFound,
    create_lead,
    get_lead_detail,
    list_leads,
    update_lead_state,
)
from app.services.storage import StorageService

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("", status_code=201, response_model=LeadRead)
async def submit_lead(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> LeadRead:
    try:
        data = LeadCreate(first_name=first_name, last_name=last_name, email=email)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_first_error(exc)) from exc

    contents = await resume.read()
    fileobj = io.BytesIO(contents)

    try:
        lead = create_lead(
            db,
            storage,
            data,
            filename=resume.filename or "",
            content_type=resume.content_type or "application/octet-stream",
            fileobj=fileobj,
            size=len(contents),
        )
    except FileValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return LeadRead.model_validate(lead)


@router.get("", response_model=list[LeadRead])
def list_all_leads(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[LeadRead]:
    leads = list_leads(db, limit=limit, offset=offset)
    return [LeadRead.model_validate(lead) for lead in leads]


@router.get("/{lead_id}", response_model=LeadDetail)
def read_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
) -> LeadDetail:
    try:
        return get_lead_detail(db, storage, lead_id)
    except LeadNotFound as exc:
        raise HTTPException(status_code=404, detail="Lead not found.") from exc


@router.patch("/{lead_id}", response_model=LeadRead)
def patch_lead(
    lead_id: uuid.UUID,
    payload: LeadStateUpdate,
    db: Session = Depends(get_db),
) -> LeadRead:
    try:
        lead = update_lead_state(db, lead_id, payload.state)
    except LeadNotFound as exc:
        raise HTTPException(status_code=404, detail="Lead not found.") from exc
    except InvalidStateTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return LeadRead.model_validate(lead)


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err.get("loc", ()))
    return f"{field}: {err.get('msg', 'invalid value')}"
