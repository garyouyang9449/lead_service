import io
import uuid

import pytest

from app.schemas.lead import LeadCreate
from app.models.lead import LeadState
from app.services.leads import (
    FileValidationError,
    LeadNotFound,
    create_lead,
    get_lead_detail,
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
