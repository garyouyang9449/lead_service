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
