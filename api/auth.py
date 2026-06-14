"""
Authentication for MyGameShelf — verifies Supabase-issued JWTs.

Each request must carry `Authorization: Bearer <access_token>` where the token
is the Supabase session access token obtained on the frontend. We verify its
signature with the project's JWT secret (HS256) and extract the user id (`sub`),
which becomes the tenant key for every query.
"""

from __future__ import annotations

import os

import jwt
from fastapi import Header, HTTPException

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
# Supabase tokens are minted with this audience for logged-in users.
JWT_AUDIENCE = "authenticated"
# Optional issuer pinning. If SUPABASE_URL is set, we additionally verify the
# token was issued by this project's auth server (defends against a token signed
# with the same secret by a different issuer). Left unset → issuer is not checked.
_SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
JWT_ISSUER = f"{_SUPABASE_URL}/auth/v1" if _SUPABASE_URL else None


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency. Returns the authenticated user's UUID, or raises 401.

    Usage:  def endpoint(..., user_id: str = Depends(get_current_user)): ...
    """
    if not SUPABASE_JWT_SECRET:
        # Misconfiguration, not a client error — fail loud so it's caught in deploy.
        raise HTTPException(
            status_code=500,
            detail="Server auth is not configured (SUPABASE_JWT_SECRET missing).",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        decode_kwargs = {
            "algorithms": ["HS256"],
            "audience": JWT_AUDIENCE,
            # Reject tokens that omit expiry or subject instead of treating them as
            # non-expiring / anonymous.
            "options": {"require": ["exp", "sub"]},
        }
        if JWT_ISSUER:
            decode_kwargs["issuer"] = JWT_ISSUER
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please log in again.")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token is missing a subject (sub) claim.")
    return user_id
