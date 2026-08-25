import os
import stripe
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from bson import ObjectId
from db import db
from deps import get_current_user
import pricing
from credits import adjust_balance
from auth import serialize_user

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

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
        metadata={"user_id": str(user["_id"]), "purpose": req.purpose, "key": req.key, "lookup_key": lookup_key},
        managed_payments={"enabled": True},
    )
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": str(user["_id"]),
        "purpose": req.purpose,
        "key": req.key,
        "lookup_key": lookup_key,
        "amount": (price.unit_amount or 0) / 100,
        "currency": price.currency,
        "status": "initiated",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return {"checkout_url": session.url, "session_id": session.id}


async def _finalize_paid_transaction(record: dict, subscription_id: str = None):
    """Runs exactly once per session (guarded by caller's payment_status transition)."""
    purpose = record.get("purpose")
    user_id = record["user_id"]
    key = record.get("key")
    if purpose == "subscription":
        tier = pricing.TIERS.get(key)
        if tier:
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"tier": key, "stripe_subscription_id": subscription_id}},
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
async def get_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                result = await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {
                        "status": "completed", "payment_status": "paid",
                        "stripe_subscription_id": s.subscription,
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )
                if result.modified_count:
                    await _finalize_paid_transaction(record, subscription_id=s.subscription)
                record = await db.payment_transactions.find_one({"session_id": session_id})
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
        record = await db.payment_transactions.find_one({"session_id": obj["id"]})
        result = await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {
                "status": "completed", "payment_status": obj.get("payment_status", "paid"),
                "stripe_subscription_id": obj.get("subscription"), "updated_at": datetime.now(timezone.utc),
            }},
        )
        if result.modified_count and record:
            await _finalize_paid_transaction(record, subscription_id=obj.get("subscription"))
    return {"status": "ok"}


@router.get("/payments/me")
async def payment_me(user=Depends(get_current_user)):
    fresh = await db.users.find_one({"_id": user["_id"]})
    return serialize_user(fresh)
