import os
import uuid

import jwt
from fastapi import HTTPException, Request

from db import get_pool

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def to_uuid(value: str, detail: str = "Not found") -> str:
    """Validate a path/body-supplied id before it reaches a query. A malformed
    value fed straight to asyncpg raises DataError, which is not an
    HTTPException and would surface as a 500 on every route that takes an id
    in its URL — this turns it into the 404 the caller deserves instead."""
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail=detail)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    subject = payload.get("sub")
    try:
        user_id = str(uuid.UUID(subject))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    pool = await get_pool()
    user = await pool.fetchrow("select * from users where id = $1", user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user)
