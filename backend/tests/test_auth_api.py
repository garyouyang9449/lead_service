def test_login_success_sets_cookie(unauthed_client, seed_user):
    _, password = seed_user
    resp = unauthed_client.post(
        "/api/auth/login",
        json={"email": "attorney@firm.com", "password": password},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "attorney@firm.com"

    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_login_wrong_password_returns_401(unauthed_client, seed_user):
    resp = unauthed_client.post(
        "/api/auth/login",
        json={"email": "attorney@firm.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert "set-cookie" not in resp.headers


def test_login_unknown_email_returns_401(unauthed_client, seed_user):
    resp = unauthed_client.post(
        "/api/auth/login",
        json={"email": "ghost@firm.com", "password": "correct-horse"},
    )
    assert resp.status_code == 401


def test_login_invalid_email_format_returns_422(unauthed_client):
    resp = unauthed_client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "x"},
    )
    assert resp.status_code == 422


def test_me_with_cookie_returns_user(unauthed_client, seed_user):
    _, password = seed_user
    unauthed_client.post(
        "/api/auth/login",
        json={"email": "attorney@firm.com", "password": password},
    )
    # TestClient persists the login cookie across requests.
    resp = unauthed_client.get("/api/auth/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "attorney@firm.com"


def test_me_with_bearer_header_returns_user(unauthed_client, seed_user):
    user, _ = seed_user
    from app.core.security import create_access_token

    token = create_access_token(str(user.id))
    resp = unauthed_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "attorney@firm.com"


def test_me_without_auth_returns_401(unauthed_client):
    resp = unauthed_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_garbage_token_returns_401(unauthed_client):
    resp = unauthed_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert resp.status_code == 401


def test_logout_clears_cookie(unauthed_client, seed_user):
    _, password = seed_user
    unauthed_client.post(
        "/api/auth/login",
        json={"email": "attorney@firm.com", "password": password},
    )
    resp = unauthed_client.post("/api/auth/logout")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    # cookie is deleted (expired / empty value)
    assert "access_token=" in set_cookie


# --- guards on internal leads routes ---


def _multipart():
    import io

    return {"resume": ("resume.pdf", io.BytesIO(b"%PDF" + b"0" * 100), "application/pdf")}


def _fields():
    return {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@calc.org"}


def test_list_leads_requires_auth(unauthed_client):
    assert unauthed_client.get("/api/leads").status_code == 401


def test_get_lead_requires_auth(unauthed_client):
    import uuid

    assert unauthed_client.get(f"/api/leads/{uuid.uuid4()}").status_code == 401


def test_patch_lead_requires_auth(unauthed_client):
    import uuid

    resp = unauthed_client.patch(
        f"/api/leads/{uuid.uuid4()}", json={"state": "REACHED_OUT"}
    )
    assert resp.status_code == 401


def test_submit_lead_is_public(unauthed_client):
    resp = unauthed_client.post("/api/leads", data=_fields(), files=_multipart())
    assert resp.status_code == 201, resp.text


def test_list_leads_with_token_succeeds(unauthed_client, seed_user):
    user, _ = seed_user
    from app.core.security import create_access_token

    token = create_access_token(str(user.id))
    resp = unauthed_client.get(
        "/api/leads", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
