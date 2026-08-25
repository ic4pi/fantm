import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
from db import db
from deps import get_current_user, get_jwt_secret, JWT_ALGORITHM
import pricing
from credits import ensure_monthly_stipend

router = APIRouter(prefix="/api/auth")

ACCESS_EXPIRE_MIN = 60 * 24
REFRESH_EXPIRE_DAYS = 7
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_EXPIRE_MIN),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, user_id: str, email: str):
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    response.set_cookie("access_token", access_token, httponly=True, secure=True, samesite="none", max_age=ACCESS_EXPIRE_MIN * 60, path="/")
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=True, samesite="none", max_age=REFRESH_EXPIRE_DAYS * 86400, path="/")


def serialize_user(user: dict) -> dict:
    tier = user.get("tier", "apprentice")
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "name": user["name"],
        "tier": tier,
        "tier_name": pricing.TIERS.get(tier, {}).get("name", tier),
        "credit_balance": user.get("credit_balance", 0),
    }


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already registered")
    now = datetime.now(timezone.utc)
    user_doc = {
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "tier": "apprentice",
        "credit_balance": pricing.TIERS["apprentice"]["stipend"],
        "last_stipend_at": now,
        "created_at": now,
    }
    res = await db.users.insert_one(user_doc)
    user_doc["_id"] = res.inserted_id
    await db.credit_transactions.insert_one({
        "user_id": str(res.inserted_id), "type": "stipend", "amount": pricing.TIERS["apprentice"]["stipend"],
        "balance_after": pricing.TIERS["apprentice"]["stipend"], "description": "Welcome stipend (Apprentice)",
        "related_book_id": None, "created_at": now,
    })
    set_auth_cookies(response, str(res.inserted_id), email)
    return serialize_user(user_doc)


@router.post("/login")
async def login(body: LoginIn, response: Response, request: Request):
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= MAX_FAILED_ATTEMPTS:
        locked_until = attempt.get("locked_until")
        if locked_until and locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(429, "Too many failed attempts. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)}},
            upsert=True,
        )
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    await ensure_monthly_stipend(user)
    set_auth_cookies(response, str(user["_id"]), email)
    return serialize_user(user)


@router.post("/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    await ensure_monthly_stipend(user)
    return serialize_user(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "User not found")
    access_token = create_access_token(str(user["_id"]), user["email"])
    response.set_cookie("access_token", access_token, httponly=True, secure=True, samesite="none", max_age=ACCESS_EXPIRE_MIN * 60, path="/")
    return serialize_user(user)
