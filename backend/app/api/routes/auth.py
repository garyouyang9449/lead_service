from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, UserRead
from app.services.auth import authenticate_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(str(user.id))
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return user


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key=settings.cookie_name, path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
