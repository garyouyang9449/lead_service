import time

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_is_not_plaintext():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert hashed.startswith("$2")  # bcrypt prefix


def test_verify_password_roundtrip():
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token("user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert "exp" in payload


def test_decode_rejects_tampered_token():
    token = create_access_token("user-123")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "tampered")


def test_decode_rejects_wrong_secret():
    bad = jwt.encode({"sub": "x"}, "not-the-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(bad)


def test_decode_rejects_expired_token():
    now = int(time.time())
    expired = jwt.encode(
        {"sub": "x", "exp": now - 10},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
