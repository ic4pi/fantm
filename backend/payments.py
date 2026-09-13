import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import pricing
from auth import serialize_user
from credits import adjust_balance
from db import get_pool
from deps import get_current_user

# No placeholder fallback: a missing key used to be swapped for a fake one, so
# a misconfigured deploy took real checkout attempts and failed at Stripe
# instead of refusing to boot. config.validate_required_env enforces presence.
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

router = APIRouter(prefix="/api")


def _resolve_lookup_key(purpose: str, key: str) -> str:
    if purpose == "subscription":
        tier = pricing.TIERS.get(key)
        if not tier or not tier.get("lookup_key"):
            raise HTTPException(400, f"Unknown subscription tier: {key}")
        return tier["lookup_key"]
    if purpose == "store":
        item = pricing.STORE_ITEMS.get(key)
        if not item:
            raise HTTPException(400, f"Unknown store item: {key}")
        return item["lookup_key"]
    if purpose == "refill":
        pack = pricing.REFILL_PACKS.get(key)
        if not pack:
            raise HTTPException(400, f"Unknown refill pack: {key}")
        return pack["lookup_key"]
    raise HTTPException(400, f"Unknown purpose: {purpose}")


class CheckoutRequest(BaseModel):
    purpose: str  # "subscription" | "store" | "refill"
    key: str  # tier key | store item key | refill pack key
    origin_url: str


@router.post("/payments/checkout")
async def create_checkout(req: CheckoutRequest, user=Depends(get_current_user)):
    lookup_key = _resolve_lookup_key(req.purpose, req.key)
    prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(400, f"Price not found: {lookup_key}")
    price = prices[0]
    session = stripe.checkout.Session.create(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription" if price.recurring else "payment",
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        metadata={"user_id": str(user["id"]), "purpose": req.purpose, "key": req.key, "lookup_key": lookup_key},
        managed_payments={"enabled": True},
    )
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    await pool.execute(
        """insert into payment_transactions (
             session_id, user_id, purpose, key, lookup_key, amount, currency,
             status, payment_status, created_at, updated_at
           ) values ($1,$2,$3,$4,$5,$6,$7,'initiated','pending',$8,$8)""",
        session.id, str(user["id"]), req.purpose, req.key, lookup_key,
        (price.unit_amount or 0) / 100, price.currency, now,
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def _finalize_paid_transaction(record: dict, subscription_id: str = None):
    """Runs exactly once per session (guarded by caller's payment_status transition)."""
    purpose = record.get("purpose")
    user_id = record["user_id"]
    key = record.get("key")
    pool = await get_pool()
    if purpose == "subscription":
        tier = pricing.TIERS.get(key)
        if tier:
            await pool.execute(
                "update users set tier=$2, stripe_subscription_id=$3 where id=$1",
                user_id, key, subscription_id,
            )
            await adjust_balance(user_id, tier["stipend"], "stipend", f"Subscription activated ({tier['name']})")
    elif purpose == "store":
        item = pricing.STORE_ITEMS.get(key)
        if item:
            await adjust_balance(user_id, item["nc"], "purchase", f"Store purchase: {item['name']}")
    elif purpose == "refill":
        pack = pricing.REFILL_PACKS.get(key)
        if pack:
            await adjust_balance(user_id, pack["nc"], "refill", f"Credit refill: {pack['name']}")


@router.get("/payments/status/{session_id}")
async def get_status(session_id: str, user=Depends(get_current_user)):
    # Authenticated and owner-scoped: this endpoint does not merely report
    # status, it settles the transaction and grants credits, so it must not be
    # reachable by anyone holding (or guessing) a session id.
    pool = await get_pool()
    record = await pool.fetchrow(
        "select * from payment_transactions where session_id = $1 and user_id = $2",
        session_id, str(user["id"]),
    )
    if not record:
        raise HTTPException(404, "Transaction not found")
    record = dict(record)
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                result = await pool.execute(
                    """update payment_transactions set status='completed', payment_status='paid',
                         stripe_subscription_id=$2, updated_at=$3
                       where session_id=$1 and payment_status != 'paid'""",
                    session_id, s.subscription, datetime.now(timezone.utc),
                )
                if result == "UPDATE 1":
                    await _finalize_paid_transaction(record, subscription_id=s.subscription)
                record = dict(await pool.fetchrow("select * from payment_transactions where session_id = $1", session_id))
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        pool = await get_pool()
        record = await pool.fetchrow("select * from payment_transactions where session_id = $1", obj["id"])
        if record:
            record = dict(record)
            result = await pool.execute(
                """update payment_transactions set status='completed', payment_status=$2,
                     stripe_subscription_id=$3, updated_at=$4
                   where session_id=$1 and payment_status != 'paid'""",
                obj["id"], obj.get("payment_status", "paid"), obj.get("subscription"), datetime.now(timezone.utc),
            )
            if result == "UPDATE 1":
                await _finalize_paid_transaction(record, subscription_id=obj.get("subscription"))
    return {"status": "ok"}


@router.get("/payments/me")
async def payment_me(user=Depends(get_current_user)):
    pool = await get_pool()
    fresh = await pool.fetchrow("select * from users where id = $1", user["id"])
    return serialize_user(dict(fresh))
