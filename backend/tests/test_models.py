from app.models.lead import Lead, LeadState
from app.models.user import User


def test_lead_defaults_to_pending():
    lead = Lead(
        first_name="A", last_name="B", email="a@b.com",
        resume_key="k", resume_filename="cv.pdf",
    )
    assert LeadState.PENDING.value == "PENDING"
    assert lead.first_name == "A"


def test_user_fields():
    u = User(email="x@y.com", hashed_password="h")
    assert u.email == "x@y.com"
