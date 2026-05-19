"""Authentication API — local email/password accounts with JWT.

Replaces the previous Supabase-hosted auth. Users register and log in here;
the server stores a bcrypt password hash and issues a signed JWT that the
frontend attaches as an `Authorization: Bearer` header on subsequent calls.

Endpoints (mounted under /api/v1):
  POST /auth/register — create an account, return a JWT + the user profile.
  POST /auth/login    — verify credentials, return a JWT + the user profile.
  GET  /auth/me       — return the profile for the bearer of a valid JWT.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.dependencies import DbSession
from app.core.security import (
    TokenData,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.postgres import UserRecord

router = APIRouter(prefix="/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class AuthResponse(BaseModel):
    """Returned by /register and /login — the token plus the user profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def _to_user_response(user: UserRecord) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    """Create a user, then issue a JWT so the client is logged in immediately."""
    email = payload.email.strip().lower()

    existing = (
        await db.execute(select(UserRecord).where(UserRecord.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = UserRecord(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    await db.flush()  # populate user.id before we build the token

    token = create_access_token(sub=str(user.id), role=user.role)
    return AuthResponse(access_token=token, user=_to_user_response(user))


@router.post("/login", response_model=AuthResponse, summary="Log in to an account")
async def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    """Verify email + password and return a fresh JWT on success."""
    email = payload.email.strip().lower()

    user = (
        await db.execute(select(UserRecord).where(UserRecord.email == email))
    ).scalar_one_or_none()
    # Same error whether the email is unknown or the password is wrong, so the
    # response does not reveal which accounts exist.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(sub=str(user.id), role=user.role)
    return AuthResponse(access_token=token, user=_to_user_response(user))


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(
    token: Annotated[TokenData, Depends(get_current_user)], db: DbSession
) -> UserResponse:
    """Return the profile of the user identified by the bearer token."""
    try:
        user_id = uuid.UUID(token.sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject.",
        )
    user = (
        await db.execute(select(UserRecord).where(UserRecord.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
        )
    return _to_user_response(user)
