import os
import jwt
from fastapi import Request, HTTPException
from bson import ObjectId
from db import db

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def to_object_id(value: str, detail: str = "Not found") -> ObjectId:
    """Parse a path/body-supplied id into an ObjectId, turning a malformed one
    into the 404 the caller deserves. Bare ObjectId() raises InvalidId, which
    is not an HTTPException and so surfaces as a 500 on every route that takes
    an id in its URL."""
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail=detail)
    return ObjectId(value)


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
    if not subject or not ObjectId.is_valid(subject):
        raise HTTPException(status_code=401, detail="Invalid token subject")
    user = await db.users.find_one({"_id": ObjectId(subject)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
