import io
import uuid


def _multipart(filename="resume.pdf", content_type="application/pdf", size=1024):
    content = b"%PDF" + b"0" * (size - 4)
    return {"resume": (filename, io.BytesIO(content), content_type)}


def _fields(first="Ada", last="Lovelace", email="ada@calc.org"):
    return {"first_name": first, "last_name": last, "email": email}


def test_create_lead_happy_path(client, fake_storage):
    resp = client.post("/api/leads", data=_fields(), files=_multipart())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["email"] == "ada@calc.org"
    assert body["state"] == "PENDING"
    assert body["resume_filename"] == "resume.pdf"
    assert uuid.UUID(body["id"])
    # the resume actually landed in storage
    assert len(fake_storage.objects) == 1


def test_create_lead_sends_prospect_confirmation_email(client, fake_email):
    resp = client.post(
        "/api/leads", data=_fields(email="ada@calc.org"), files=_multipart()
    )
    assert resp.status_code == 201, resp.text

    recipients = [to for to, _, _ in fake_email.sent]
    assert recipients == ["ada@calc.org"]


def test_create_lead_rejects_bad_extension(client):
    resp = client.post(
        "/api/leads",
        data=_fields(),
        files=_multipart(filename="x.exe", content_type="application/octet-stream"),
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_create_lead_rejects_oversized(client):
    resp = client.post(
        "/api/leads",
        data=_fields(),
        files=_multipart(size=6 * 1024 * 1024),
    )
    assert resp.status_code == 422


def test_create_lead_rejects_invalid_email(client):
    resp = client.post(
        "/api/leads",
        data=_fields(email="not-an-email"),
        files=_multipart(),
    )
    assert resp.status_code == 422


def test_create_lead_requires_file(client):
    resp = client.post("/api/leads", data=_fields())
    assert resp.status_code == 422


def test_get_lead_detail_returns_presigned_url(client):
    created = client.post("/api/leads", data=_fields(), files=_multipart()).json()
    resp = client.get(f"/api/leads/{created['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["resume_url"].startswith("https://")


def test_get_lead_detail_not_found(client):
    resp = client.get(f"/api/leads/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_leads_returns_created_leads(client):
    client.post("/api/leads", data=_fields(email="a@x.org"), files=_multipart())
    client.post("/api/leads", data=_fields(email="b@x.org"), files=_multipart())

    resp = client.get("/api/leads")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    emails = {l["email"] for l in body}
    assert emails == {"a@x.org", "b@x.org"}
    # list items carry full prospect info + state, but no presigned url
    assert "state" in body[0]
    assert "resume_filename" in body[0]
    assert "resume_url" not in body[0]


def test_list_leads_empty(client):
    resp = client.get("/api/leads")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_leads_pagination(client):
    for i in range(3):
        client.post("/api/leads", data=_fields(email=f"u{i}@x.org"), files=_multipart())

    resp = client.get("/api/leads?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_patch_lead_marks_reached_out(client):
    created = client.post("/api/leads", data=_fields(), files=_multipart()).json()
    assert created["state"] == "PENDING"

    resp = client.patch(f"/api/leads/{created['id']}", json={"state": "REACHED_OUT"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "REACHED_OUT"

    # persisted: subsequent GET reflects new state
    detail = client.get(f"/api/leads/{created['id']}").json()
    assert detail["state"] == "REACHED_OUT"


def test_patch_lead_invalid_transition_returns_409(client):
    created = client.post("/api/leads", data=_fields(), files=_multipart()).json()
    client.patch(f"/api/leads/{created['id']}", json={"state": "REACHED_OUT"})

    # already REACHED_OUT -> REACHED_OUT is invalid
    resp = client.patch(f"/api/leads/{created['id']}", json={"state": "REACHED_OUT"})
    assert resp.status_code == 409
    assert "detail" in resp.json()


def test_patch_lead_back_to_pending_returns_409(client):
    created = client.post("/api/leads", data=_fields(), files=_multipart()).json()
    client.patch(f"/api/leads/{created['id']}", json={"state": "REACHED_OUT"})

    resp = client.patch(f"/api/leads/{created['id']}", json={"state": "PENDING"})
    assert resp.status_code == 409


def test_patch_lead_not_found_returns_404(client):
    resp = client.patch(f"/api/leads/{uuid.uuid4()}", json={"state": "REACHED_OUT"})
    assert resp.status_code == 404


def test_patch_lead_invalid_state_value_returns_422(client):
    created = client.post("/api/leads", data=_fields(), files=_multipart()).json()
    resp = client.patch(f"/api/leads/{created['id']}", json={"state": "BOGUS"})
    assert resp.status_code == 422
