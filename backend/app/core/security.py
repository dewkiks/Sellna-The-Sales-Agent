"""JWT-based authentication & authorization.

JSON Web Tokens (JWTs) are self-contained signed tokens.  A client logs in
once, receives a token, and includes it as an HTTP Bearer header on subsequent
requests.  The server verifies the signature (using SECRET_KEY) and reads the
claims (sub, role, exp) without hitting the database on every request.

Token lifecycle:
  1. ``create_access_token(sub, role)`` — called by a login/bootstrap endpoint;
     returns a signed JWT valid for JWT_EXPIRE_MINUTES (default 24 h).
  2. ``_get_current_token(credentials)`` — FastAPI dependency; extracts and
     verifies the token from the Authorization: Bearer header.  Raises 401 if
     the token is missing, malformed, or expired.
  3. ``require_role(*roles)`` — dependency factory; wraps _get_current_token and
     additionally checks that token.role is in the allowed set.  Raises 403 if
     not.  Example:

        @router.get("/admin-only")
        async def admin_route(user: TokenData = Depends(require_role("admin"))):
            ...

Supported roles:
  - "admin"   — full access (human users)
  - "service" — machine-to-machine calls between internal services
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

_settings = get_settings()
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# bcrypt only inspects the first 72 bytes of a password; longer inputs raise
# in modern bcrypt, so we truncate explicitly to keep hashing deterministic.
_BCRYPT_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    """Encode a password and clamp it to bcrypt's 72-byte working limit."""
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of ``plain`` suitable for storing in the DB."""
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if ``plain`` matches the stored bcrypt ``hashed`` value."""
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/empty stored hash — treat as a failed match, never raise.
        return False


# ---------------------------------------------------------------------------
# Token model
# ---------------------------------------------------------------------------


class TokenData(BaseModel):
    """Parsed claims extracted from a verified JWT.

    Attributes:
        sub:  Subject — the user ID or service name encoded in the token.
        role: The role granted to this token ("admin" or "service").
        exp:  Expiry datetime (UTC); python-jose validates this automatically
              during decoding but we store it here for downstream inspection.
    """

    sub: str  # user_id or service name
    role: str  # "admin" | "service"
    exp: datetime


# ---------------------------------------------------------------------------
# Token creation (used by login/bootstrap endpoints)
# ---------------------------------------------------------------------------


def create_access_token(sub: str, role: str = "admin") -> str:
    """Return a signed JWT access token.

    Args:
        sub:  The subject claim — typically a user ID or service identifier.
        role: Role to embed in the token; defaults to "admin".

    Returns:
        A URL-safe JWT string.  The token is signed with HS256 (HMAC-SHA256)
        using SECRET_KEY.  python-jose encodes the payload as Base64URL JSON.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_settings.jwt_expire_minutes)
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,    # issued-at — informational
        "exp": expire, # expiry — python-jose enforces this on decode
    }
    return jwt.encode(payload, _settings.secret_key, algorithm=_settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


async def _get_current_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenData:
    """FastAPI dependency: extract and verify the Bearer JWT from the request.

    HTTPBearer with ``auto_error=False`` means FastAPI will not automatically
    reject requests without a header; we handle the missing case ourselves so
    we can return a more descriptive error message.

    Args:
        credentials: Parsed Authorization header from HTTPBearer, or None.

    Returns:
        A populated TokenData if the token is valid and not expired.

    Raises:
        HTTPException 401: Token missing, expired, or signature invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        # jwt.decode validates signature, expiry (exp), and algorithm.
        payload = jwt.decode(
            credentials.credentials,
            _settings.secret_key,
            algorithms=[_settings.jwt_algorithm],
        )
        return TokenData(
            sub=payload["sub"],
            role=payload.get("role", "admin"),  # fall back to admin if claim absent
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except JWTError as exc:
        # JWTError covers expired tokens, bad signatures, malformed headers, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*roles: str):
    """FastAPI dependency factory for role-based access control.

    Returns a new async dependency function that first verifies the JWT
    (via _get_current_token) and then confirms the embedded role is one
    of the allowed values.

    Args:
        *roles: One or more role names that are permitted to access the route.

    Returns:
        An async dependency callable suitable for use with Depends().

    Raises:
        HTTPException 401: Token is invalid (delegated to _get_current_token).
        HTTPException 403: Token is valid but the role is not in ``roles``.

    Example:
        async def admin_route(user=Depends(require_role("admin"))): ...
    """

    async def _check(token: Annotated[TokenData, Depends(_get_current_token)]) -> TokenData:
        # _get_current_token already ran — token is valid at this point.
        if token.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{token.role}' is not allowed. Required: {roles}",
            )
        return token

    return _check


# Convenience shorthand — use when you only need authentication, not a specific role.
get_current_user = _get_current_token
