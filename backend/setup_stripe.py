import os
import stripe
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"

CATALOG = [
    {
        "emergent_product_id": "fantm_tier_wordsmith",
        "name": "fantm.ink — Wordsmith",
        "tax_code": "txcd_10103001",
        "prices": [{"lookup_key": "wordsmith_monthly", "amount": 900, "currency": "usd", "interval": "month"}],
    },
    {
        "emergent_product_id": "fantm_tier_laureate",
        "name": "fantm.ink — Laureate",
        "tax_code": "txcd_10103001",
        "prices": [{"lookup_key": "laureate_monthly", "amount": 3300, "currency": "usd", "interval": "month"}],
    },
    {
        "emergent_product_id": "fantm_store_writer_pack",
        "name": "Professional Writer Pack (10,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "store_writer_pack", "amount": 500, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_store_genre_expansion",
        "name": "Genre Expansion (15,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "store_genre_expansion", "amount": 750, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_store_visual_prop",
        "name": "Visual Prop / Book Cover (2,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "store_visual_prop", "amount": 100, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_store_full_layout",
        "name": "Full Project Layout & Legal (5,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "store_full_layout", "amount": 250, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_store_full_library",
        "name": "Full Library Unlock (50,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "store_full_library", "amount": 2500, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_refill_small",
        "name": "Small Stack (10,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "refill_small", "amount": 500, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_refill_medium",
        "name": "Medium Stack (50,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "refill_medium", "amount": 2200, "currency": "usd"}],
    },
    {
        "emergent_product_id": "fantm_refill_large",
        "name": "Large Stack (120,000 NC)",
        "tax_code": "txcd_10000000",
        "prices": [{"lookup_key": "refill_large", "amount": 4500, "currency": "usd"}],
    },
]


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(
        name=entry["name"],
        tax_code=entry.get("tax_code"),
        metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
    )


def ensure_price(product, p):
    existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
    if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
        stripe.Price.modify(existing[0].id, active=False)
        existing = []
    if not existing:
        kwargs = dict(
            product=product.id, unit_amount=p["amount"], currency=p["currency"],
            lookup_key=p["lookup_key"], transfer_lookup_key=True,
        )
        if p.get("interval"):
            kwargs["recurring"] = {"interval": p["interval"]}
        stripe.Price.create(**kwargs)


def ensure_tax_settings():
    s = stripe.tax.Settings.retrieve()
    if s.head_office and getattr(s.head_office, "address", None):
        return
    stripe.tax.Settings.modify(
        head_office={"address": {"country": "US", "line1": "123 Market St", "city": "San Francisco", "state": "CA", "postal_code": "94103"}},
        defaults={"tax_behavior": "exclusive"},
    )


if __name__ == "__main__":
    ensure_tax_settings()
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for p in entry["prices"]:
            ensure_price(product, p)
    print("Stripe catalog setup complete.")
