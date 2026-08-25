from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from bson import ObjectId
from db import db
from deps import get_current_user
import pricing

router = APIRouter(prefix="/api/credits")


async def get_balance(user_id: str) -> int:
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"credit_balance": 1})
    return (user or {}).get("credit_balance", 0)


async def adjust_balance(user_id: str, amount: int, tx_type: str, description: str, related_book_id: str = None) -> int:
    updated = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$inc": {"credit_balance": amount}},
        return_document=True,
    )
    new_balance = updated.get("credit_balance", 0) if updated else 0
    await db.credit_transactions.insert_one({
        "user_id": user_id,
        "type": tx_type,
        "amount": amount,
        "balance_after": new_balance,
        "description": description,
        "related_book_id": related_book_id,
        "created_at": datetime.now(timezone.utc),
    })
    return new_balance


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def ensure_monthly_stipend(user: dict):
    tier = user.get("tier", "apprentice")
    stipend = pricing.TIERS.get(tier, pricing.TIERS["apprentice"])["stipend"]
    last = _aware(user.get("last_stipend_at"))
    now = datetime.now(timezone.utc)
    if last is None or (now - last) >= timedelta(days=pricing.STIPEND_INTERVAL_DAYS):
        tier_name = pricing.TIERS.get(tier, {}).get("name", tier)
        await adjust_balance(str(user["_id"]), stipend, "stipend", f"Monthly stipend ({tier_name})")
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"last_stipend_at": now}})
        user["last_stipend_at"] = now


@router.get("/balance")
async def balance(user=Depends(get_current_user)):
    await ensure_monthly_stipend(user)
    fresh = await db.users.find_one({"_id": user["_id"]})
    tier = fresh.get("tier", "apprentice")
    return {
        "balance": fresh.get("credit_balance", 0),
        "tier": tier,
        "tier_name": pricing.TIERS.get(tier, {}).get("name", tier),
        "monthly_stipend": pricing.TIERS.get(tier, {}).get("stipend", 0),
    }


@router.get("/transactions")
async def transactions(user=Depends(get_current_user)):
    txs = await db.credit_transactions.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(50)
    return [{
        "id": str(t["_id"]),
        "type": t["type"],
        "amount": t["amount"],
        "balance_after": t["balance_after"],
        "description": t["description"],
        "created_at": t["created_at"].isoformat(),
    } for t in txs]


@router.get("/styles")
async def styles(user=Depends(get_current_user)):
    tier = user.get("tier", "apprentice")
    allowed = set(pricing.allowed_styles_for_tier(tier))
    out = [
        {"key": k, "name": v["name"], "multiplier": v["multiplier"], "tier_req": v["tier_req"], "unlocked": k in allowed}
        for k, v in pricing.WRITER_STYLES.items()
    ]
    chimera_lo, chimera_hi = pricing.chimera_multiplier_range()
    out.append({
        "key": pricing.CHIMERA_KEY, "name": pricing.CHIMERA_NAME,
        "multiplier_min": chimera_lo, "multiplier_max": chimera_hi,
        "tier_req": pricing.CHIMERA_TIER_REQ, "unlocked": pricing.CHIMERA_KEY in allowed,
    })
    return out


@router.get("/tiers")
async def tiers():
    return [{"key": k, **v} for k, v in pricing.TIERS.items()]


@router.get("/store")
async def store():
    return [{"key": k, **v} for k, v in pricing.STORE_ITEMS.items()]


@router.get("/refill-packs")
async def refill_packs():
    return [{"key": k, **v} for k, v in pricing.REFILL_PACKS.items()]
