import io
import uuid

import pytest

from app.schemas.lead import LeadCreate
from app.models.lead import LeadState
from app.services.leads import (
    FileValidationError,
    InvalidStateTransition,
    LeadNotFound,
    create_lead,
    get_lead_detail,
    list_leads,
    update_lead_state,
    validate_resume,
)


def _pdf(size_bytes: int = 10) -> io.BytesIO:
    return io.BytesIO(b"%PDF" + b"0" * (size_bytes - 4))


# ---- validate_resume ----

def test_validate_resume_accepts_pdf():
    validate_resume("cv.pdf", "application/pdf", 1024)  # no raise


def test_validate_resume_accepts_docx():
    validate_resume(
        "cv.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        1024,
    )


def test_validate_resume_rejects_bad_extension():
    with pytest.raises(FileValidationError):
        validate_resume("cv.exe", "application/octet-stream", 1024)


def test_validate_resume_rejects_oversized():
    with pytest.raises(FileValidationError):
        validate_resume("cv.pdf", "application/pdf", 6 * 1024 * 1024)


def test_validate_resume_rejects_empty():
    with pytest.raises(FileValidationError):
        validate_resume("cv.pdf", "application/pdf", 0)


# ---- create_lead ----

def test_create_lead_persists_and_uploads(db_session, fake_storage):
    data = LeadCreate(first_name="Ada", last_name="Lovelace", email="ada@calc.org")
    lead = create_lead(
        db_session,
        fake_storage,
        data,
        filename="resume.pdf",
        content_type="application/pdf",
        fileobj=_pdf(20),
        size=20,
    )

    assert lead.id is not None
    assert lead.first_name == "Ada"
    assert lead.state == LeadState.PENDING
    assert lead.resume_filename == "resume.pdf"
    # key namespaced under the lead id
    assert lead.resume_key == f"leads/{lead.id}/resume.pdf"
    # file actually handed to storage under that key
    assert lead.resume_key in fake_storage.objects


def test_create_lead_rejects_invalid_file(db_session, fake_storage):
    data = LeadCreate(first_name="Ada", last_name="Lovelace", email="ada@calc.org")
    with pytest.raises(FileValidationError):
        create_lead(
            db_session,
            fake_storage,
            data,
            filename="malware.exe",
            content_type="application/octet-stream",
            fileobj=_pdf(20),
            size=20,
        )
    # nothing stored, nothing persisted
    assert fake_storage.objects == {}


# ---- get_lead_detail ----

def test_get_lead_detail_returns_presigned_url(db_session, fake_storage):
    data = LeadCreate(first_name="Ada", last_name="Lovelace", email="ada@calc.org")
    lead = create_lead(
        db_session, fake_storage, data,
        filename="resume.pdf", content_type="application/pdf",
        fileobj=_pdf(20), size=20,
    )
    detail = get_lead_detail(db_session, fake_storage, lead.id)
    assert detail.id == lead.id
    assert detail.resume_url == fake_storage.presigned_url(lead.resume_key)


def test_get_lead_detail_missing_raises(db_session, fake_storage):
    with pytest.raises(LeadNotFound):
        get_lead_detail(db_session, fake_storage, uuid.uuid4())


# ---- list_leads ----

from datetime import datetime, timedelta, timezone


def _make(db, storage, first, created_at=None):
    data = LeadCreate(first_name=first, last_name="X", email=f"{first}@x.org")
    lead = create_lead(
        db, storage, data,
        filename="r.pdf", content_type="application/pdf",
        fileobj=_pdf(20), size=20,
    )
    if created_at is not None:
        lead.created_at = created_at
        db.commit()
        db.refresh(lead)
    return lead


def test_list_leads_returns_all_newest_first(db_session, fake_storage):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _make(db_session, fake_storage, "alice", base)
    b = _make(db_session, fake_storage, "bob", base + timedelta(minutes=1))
    c = _make(db_session, fake_storage, "carol", base + timedelta(minutes=2))

    result = list_leads(db_session)

    assert [l.id for l in result] == [c.id, b.id, a.id]


def test_list_leads_empty(db_session, fake_storage):
    assert list_leads(db_session) == []


def test_list_leads_respects_limit_and_offset(db_session, fake_storage):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = _make(db_session, fake_storage, "alice", base)
    b = _make(db_session, fake_storage, "bob", base + timedelta(minutes=1))
    c = _make(db_session, fake_storage, "carol", base + timedelta(minutes=2))

    # newest-first: [carol, bob, alice]; offset 1, limit 1 -> bob
    page = list_leads(db_session, limit=1, offset=1)

    assert [l.id for l in page] == [b.id]


# ---- update_lead_state ----

def test_update_lead_state_pending_to_reached_out(db_session, fake_storage):
    lead = _make(db_session, fake_storage, "alice")
    assert lead.state == LeadState.PENDING

    updated = update_lead_state(db_session, lead.id, LeadState.REACHED_OUT)

    assert updated.state == LeadState.REACHED_OUT
    # persisted
    db_session.refresh(lead)
    assert lead.state == LeadState.REACHED_OUT


def test_update_lead_state_rejects_reached_out_to_pending(db_session, fake_storage):
    lead = _make(db_session, fake_storage, "alice")
    update_lead_state(db_session, lead.id, LeadState.REACHED_OUT)

    with pytest.raises(InvalidStateTransition):
        update_lead_state(db_session, lead.id, LeadState.PENDING)


def test_update_lead_state_rejects_reached_out_to_reached_out(db_session, fake_storage):
    lead = _make(db_session, fake_storage, "alice")
    update_lead_state(db_session, lead.id, LeadState.REACHED_OUT)

    with pytest.raises(InvalidStateTransition):
        update_lead_state(db_session, lead.id, LeadState.REACHED_OUT)


def test_update_lead_state_rejects_pending_to_pending(db_session, fake_storage):
    lead = _make(db_session, fake_storage, "alice")

    with pytest.raises(InvalidStateTransition):
        update_lead_state(db_session, lead.id, LeadState.PENDING)


def test_update_lead_state_missing_lead_raises(db_session, fake_storage):
    with pytest.raises(LeadNotFound):
        update_lead_state(db_session, uuid.uuid4(), LeadState.REACHED_OUT)
