from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends

import pricing
from db import get_pool
from deps import get_current_user

router = APIRouter(prefix="/api/credits")


async def get_balance(user_id: str) -> int:
    pool = await get_pool()
    return await pool.fetchval("select credit_balance from users where id = $1", user_id) or 0


async def _log_transaction(user_id: str, amount: int, tx_type: str, description: str,
                            balance_after: int, related_book_id: str = None):
    pool = await get_pool()
    await pool.execute(
        """insert into credit_transactions (user_id, type, amount, balance_after, description, related_book_id)
           values ($1, $2, $3, $4, $5, $6)""",
        user_id, tx_type, amount, balance_after, description, related_book_id,
    )


async def adjust_balance(user_id: str, amount: int, tx_type: str, description: str, related_book_id: str = None) -> int:
    """Unguarded balance change. Only safe for credits *added* (stipends,
    purchases, refunds) or for debits whose affordability was already
    established atomically. To spend credits, use reserve_credits."""
    pool = await get_pool()
    new_balance = await pool.fetchval(
        "update users set credit_balance = credit_balance + $2 where id = $1 returning credit_balance",
        user_id, amount,
    )
    new_balance = new_balance if new_balance is not None else 0
    await _log_transaction(user_id, amount, tx_type, description, new_balance, related_book_id)
    return new_balance


async def reserve_credits(user_id: str, amount: int, description: str,
                           tx_type: str = "hold", related_book_id: str = None) -> Optional[int]:
    """Atomically debit `amount`, but only if the balance actually covers it.
    Returns the new balance, or None when the user can't afford it.

    The affordability check lives in the update's WHERE clause, not in a
    separate read beforehand: concurrent requests would each pass their own
    read-then-write check and drive the balance negative. Spending is always
    a reservation taken up front, then reconciled against real usage by
    settle_reservation once the work is done."""
    if amount <= 0:
        return await get_balance(user_id)
    pool = await get_pool()
    new_balance = await pool.fetchval(
        "update users set credit_balance = credit_balance - $2 where id = $1 and credit_balance >= $2 returning credit_balance",
        user_id, amount,
    )
    if new_balance is None:
        return None
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
    go negative on. One statement: the old balance is read and the new one
    written under the same row lock, so a concurrent change can't overdraw
    it — no compare-and-swap retry loop needed."""
    if amount <= 0:
        return await get_balance(user_id)
    pool = await get_pool()
    row = await pool.fetchrow(
        """with old as (select credit_balance from users where id = $1 for update)
           update users set credit_balance = greatest(users.credit_balance - $2, 0)
           from old
           where users.id = $1
           returning users.credit_balance as new_balance, old.credit_balance as old_balance""",
        user_id, amount,
    )
    if row is None:
        return 0
    taken = row["old_balance"] - row["new_balance"]
    if taken > 0:
        await _log_transaction(user_id, -taken, tx_type, description, row["new_balance"], related_book_id)
    return row["new_balance"]


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
        await adjust_balance(str(user["id"]), stipend, "stipend", f"Monthly stipend ({tier_name})")
        pool = await get_pool()
        await pool.execute("update users set last_stipend_at = $2 where id = $1", str(user["id"]), now)
        user["last_stipend_at"] = now


@router.get("/balance")
async def balance(user=Depends(get_current_user)):
    await ensure_monthly_stipend(user)
    pool = await get_pool()
    fresh = await pool.fetchrow("select * from users where id = $1", str(user["id"]))
    tier = fresh["tier"]
    return {
        "balance": fresh["credit_balance"],
        "tier": tier,
        "tier_name": pricing.TIERS.get(tier, {}).get("name", tier),
        "monthly_stipend": pricing.TIERS.get(tier, {}).get("stipend", 0),
    }


@router.get("/transactions")
async def transactions(user=Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select * from credit_transactions where user_id = $1 order by created_at desc limit 50",
        str(user["id"]),
    )
    return [{
        "id": str(t["id"]),
        "type": t["type"],
        "amount": t["amount"],
        "balance_after": t["balance_after"],
        "description": t["description"],
        "created_at": t["created_at"].isoformat(),
    } for t in rows]


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
