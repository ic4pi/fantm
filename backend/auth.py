import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

import pricing
from credits import ensure_monthly_stipend
from db import get_pool
from deps import JWT_ALGORITHM, get_current_user, get_jwt_secret

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
        "id": str(user["id"]),
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
    pool = await get_pool()
    existing = await pool.fetchval("select 1 from users where email = $1", email)
    if existing:
        raise HTTPException(400, "Email already registered")
    now = datetime.now(timezone.utc)
    stipend = pricing.TIERS["apprentice"]["stipend"]
    row = await pool.fetchrow(
        """insert into users (email, password_hash, name, tier, credit_balance, last_stipend_at, created_at)
           values ($1, $2, $3, 'apprentice', $4, $5, $5)
           returning *""",
        email, hash_password(body.password), body.name, stipend, now,
    )
    user = dict(row)
    await pool.execute(
        """insert into credit_transactions (user_id, type, amount, balance_after, description, related_book_id, created_at)
           values ($1, 'stipend', $2, $2, 'Welcome stipend (Apprentice)', null, $3)""",
        str(user["id"]), stipend, now,
    )
    set_auth_cookies(response, str(user["id"]), email)
    return serialize_user(user)


@router.post("/login")
async def login(body: LoginIn, response: Response, request: Request):
    email = body.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    pool = await get_pool()
    attempt = await pool.fetchrow("select * from login_attempts where identifier = $1", identifier)
    if attempt and attempt["count"] >= MAX_FAILED_ATTEMPTS:
        locked_until = attempt["locked_until"]
        if locked_until and locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(429, "Too many failed attempts. Try again later.")
    user_row = await pool.fetchrow("select * from users where email = $1", email)
    if not user_row or not verify_password(body.password, user_row["password_hash"]):
        await pool.execute(
            """insert into login_attempts (identifier, count, locked_until) values ($1, 1, $2)
               on conflict (identifier) do update
                 set count = login_attempts.count + 1, locked_until = excluded.locked_until""",
            identifier, datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES),
        )
        raise HTTPException(401, "Invalid email or password")
    await pool.execute("delete from login_attempts where identifier = $1", identifier)
    user = dict(user_row)
    await ensure_monthly_stipend(user)
    set_auth_cookies(response, str(user["id"]), email)
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
    subject = payload.get("sub")
    try:
        user_id = str(uuid.UUID(subject))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(401, "Invalid refresh token")
    pool = await get_pool()
    user_row = await pool.fetchrow("select * from users where id = $1", user_id)
    if not user_row:
        raise HTTPException(401, "User not found")
    user = dict(user_row)
    access_token = create_access_token(str(user["id"]), user["email"])
    response.set_cookie("access_token", access_token, httponly=True, secure=True, samesite="none", max_age=ACCESS_EXPIRE_MIN * 60, path="/")
    return serialize_user(user)
