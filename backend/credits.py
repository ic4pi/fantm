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


async def _log_transaction(user_id: str, amount: int, tx_type: str, description: str,
                          balance_after: int, related_book_id: str = None):
    await db.credit_transactions.insert_one({
        "user_id": user_id,
        "type": tx_type,
        "amount": amount,
        "balance_after": balance_after,
        "description": description,
        "related_book_id": related_book_id,
        "created_at": datetime.now(timezone.utc),
    })


async def adjust_balance(user_id: str, amount: int, tx_type: str, description: str, related_book_id: str = None) -> int:
    """Unguarded balance change. Only safe for credits *added* (stipends,
    purchases, refunds) or for debits whose affordability was already
    established atomically. To spend credits, use reserve_credits."""
    updated = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$inc": {"credit_balance": amount}},
        return_document=True,
    )
    new_balance = updated.get("credit_balance", 0) if updated else 0
    await _log_transaction(user_id, amount, tx_type, description, new_balance, related_book_id)
    return new_balance


async def reserve_credits(user_id: str, amount: int, description: str,
                          tx_type: str = "hold", related_book_id: str = None):
    """Atomically debit `amount`, but only if the balance actually covers it.
    Returns the new balance, or None when the user can't afford it.

    The affordability check lives in the update *filter*, not in a separate
    read beforehand: concurrent requests would each pass their own
    read-then-write check and drive the balance negative. Spending is always
    a reservation taken up front, then reconciled against real usage by
    settle_reservation once the work is done."""
    if amount <= 0:
        return await get_balance(user_id)
    updated = await db.users.find_one_and_update(
        {"_id": ObjectId(user_id), "credit_balance": {"$gte": amount}},
        {"$inc": {"credit_balance": -amount}},
        return_document=True,
    )
    if updated is None:
        return None
    new_balance = updated.get("credit_balance", 0)
    await _log_transaction(user_id, -amount, tx_type, description, new_balance, related_book_id)
    return new_balance


async def release_reservation(user_id: str, amount: int, description: str, related_book_id: str = None) -> int:
    """Hand back a reservation that was never consumed (the work failed to
    start at all)."""
    if amount <= 0:
        return await get_balance(user_id)
    return await adjust_balance(user_id, amount, "refund", description, related_book_id)


async def charge_capped(user_id: str, amount: int, tx_type: str, description: str, related_book_id: str = None) -> int:
    """Debit up to `amount` without ever pushing the balance below zero.

    Used only to settle an overage: the reservation already covered the
    estimate, so a shortfall beyond it is ours to absorb, not the user's to
    go negative on. Compare-and-swap on the exact balance we read, retried,
    so a concurrent change can't clobber this or overdraw."""
    if amount <= 0:
        return await get_balance(user_id)
    oid = ObjectId(user_id)
    for _ in range(5):
        current = await get_balance(user_id)
        take = min(amount, max(current, 0))
        if take <= 0:
            return current
        updated = await db.users.find_one_and_update(
            {"_id": oid, "credit_balance": current},
            {"$inc": {"credit_balance": -take}},
            return_document=True,
        )
        if updated is not None:
            new_balance = updated.get("credit_balance", 0)
            await _log_transaction(user_id, -take, tx_type, description, new_balance, related_book_id)
            return new_balance
    return await get_balance(user_id)


async def settle_reservation(user_id: str, reserved: int, actual: int, description: str,
                             related_book_id: str = None) -> int:
    """Reconcile a hold against what the work actually consumed: refund the
    unused remainder, or collect the overage (capped at the balance)."""
    delta = reserved - actual
    if delta > 0:
        return await adjust_balance(user_id, delta, "refund", description, related_book_id)
    if delta < 0:
        return await charge_capped(user_id, -delta, "burn", description, related_book_id)
    return await get_balance(user_id)


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
