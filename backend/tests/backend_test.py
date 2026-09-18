"""
Backend regression tests for fantm.ink (AI Book Generation SaaS).

Iteration 3: NEW Neural Credit (NC) economy.
- Tiers: apprentice/wordsmith/laureate (replaces free/premium)
- Styles: house/anne_rousseau/raymond_chandley/joan_dedion/edgar_rhys_burrows + chimera
- Store: 5 items, 3 refill packs
- NEW endpoints: /api/credits/{balance,transactions,styles,tiers,store,refill-packs}
- POST /api/payments/checkout now takes {purpose, key, origin_url}
- POST /api/books validates style vs tier, returns 402 (not 403) on insufficient NC
- POST /api/books/{id}/unlock-illustrations (2000 NC)
- GET /api/books/{id}/pdf costs 5000 NC (idempotent)
- PATCH chapter has NO tier gate now (any tier can edit)
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

EXISTING_USER = {"email": "tester1@fantm.ink", "password": "testpass123"}
LAUREATE_BOOK_ID = "6a74bc8109ac96789a7c87e2"  # 'The Whispering Light', chimera


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def laureate_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=EXISTING_USER, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def fresh_apprentice():
    """Register a fresh Apprentice (free) user."""
    email = f"test_{uuid.uuid4().hex[:10]}@fantm.ink"
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "testpass123", "name": "TEST Apprentice"},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return {"session": s, "email": email, "data": r.json()}


# ---------- auth + registration stipend ----------


class TestAuthAndStipend:
    def test_register_grants_apprentice_stipend(self, fresh_apprentice):
        data = fresh_apprentice["data"]
        assert data["tier"] == "apprentice"
        assert data["tier_name"] == "Apprentice"
        assert data["credit_balance"] == 5000
        assert "premium_active" not in data  # old field removed
        # cookies set
        c = fresh_apprentice["session"].cookies.get_dict()
        assert "access_token" in c and "refresh_token" in c

    def test_me_returns_new_tier_fields(self, fresh_apprentice):
        r = fresh_apprentice["session"].get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "apprentice"
        assert d["credit_balance"] >= 5000

    def test_welcome_ledger_transaction_recorded(self, fresh_apprentice):
        r = fresh_apprentice["session"].get(f"{BASE_URL}/api/credits/transactions", timeout=15)
        assert r.status_code == 200
        txs = r.json()
        assert len(txs) >= 1
        welcome = txs[-1]  # oldest last (sorted desc, so this is oldest of returned)
        # actually descending; first item is newest. The welcome should exist somewhere
        assert any(t["type"] == "stipend" and t["amount"] == 5000 for t in txs)

    def test_laureate_user_has_expected_tier(self, laureate_session):
        r = laureate_session.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["tier"] == "laureate", f"tester1 must be laureate, got {d['tier']}"
        assert d["credit_balance"] > 0


# ---------- credits catalog endpoints ----------


class TestCreditsEndpoints:
    def test_balance_endpoint(self, fresh_apprentice):
        r = fresh_apprentice["session"].get(f"{BASE_URL}/api/credits/balance", timeout=15)
        assert r.status_code == 200
        b = r.json()
        assert b["tier"] == "apprentice"
        assert b["tier_name"] == "Apprentice"
        assert b["monthly_stipend"] == 5000
        assert b["balance"] >= 5000

    def test_tiers_endpoint_returns_three(self):
        r = requests.get(f"{BASE_URL}/api/credits/tiers", timeout=15)
        assert r.status_code == 200
        tiers = r.json()
        keys = {t["key"] for t in tiers}
        assert keys == {"apprentice", "wordsmith", "laureate"}
        by_key = {t["key"]: t for t in tiers}
        assert by_key["apprentice"]["stipend"] == 5000
        assert by_key["wordsmith"]["stipend"] == 40000
        assert by_key["wordsmith"]["price_usd"] == 9
        assert by_key["laureate"]["stipend"] == 150000
        assert by_key["laureate"]["price_usd"] == 33

    def test_store_endpoint_returns_five_items(self):
        r = requests.get(f"{BASE_URL}/api/credits/store", timeout=15)
        assert r.status_code == 200
        items = r.json()
        keys = {i["key"] for i in items}
        assert keys == {"writer_pack", "genre_expansion", "visual_prop", "full_layout", "full_library"}

    def test_refill_packs_returns_three(self):
        r = requests.get(f"{BASE_URL}/api/credits/refill-packs", timeout=15)
        assert r.status_code == 200
        packs = r.json()
        keys = {p["key"] for p in packs}
        assert keys == {"small", "medium", "large"}

    def test_apprentice_styles_only_house_unlocked(self, fresh_apprentice):
        r = fresh_apprentice["session"].get(f"{BASE_URL}/api/credits/styles", timeout=15)
        assert r.status_code == 200
        styles = {s["key"]: s for s in r.json()}
        assert styles["house"]["unlocked"] is True
        assert styles["anne_rousseau"]["unlocked"] is False
        assert styles["raymond_chandley"]["unlocked"] is False
        assert styles["joan_dedion"]["unlocked"] is False
        assert styles["edgar_rhys_burrows"]["unlocked"] is False
        assert styles["chimera"]["unlocked"] is False
        assert styles["chimera"]["multiplier"] == 2.0

    def test_laureate_styles_all_unlocked(self, laureate_session):
        r = laureate_session.get(f"{BASE_URL}/api/credits/styles", timeout=15)
        assert r.status_code == 200
        for s in r.json():
            assert s["unlocked"] is True, f"laureate missing style {s['key']}"


# ---------- books + style/credit gating ----------


class TestBookCreationGating:
    def test_apprentice_locked_style_returns_403(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/books",
            json={
                "book_type": "novel",
                "prompt": "TEST locked-style attempt as apprentice.",
                "genre": "test", "tone": "test",
                "length": "short", "style": "anne_rousseau",
            },
            timeout=20,
        )
        assert r.status_code == 403
        assert "higher tier" in (r.json().get("detail") or "").lower() or "style" in (r.json().get("detail") or "").lower()

    def test_apprentice_insufficient_credits_returns_402(self, fresh_apprentice):
        # Long house-style book costs ~12*900*1.0 = 10800 NC > 5000 NC stipend.
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/books",
            json={
                "book_type": "novel",
                "prompt": "TEST apprentice cannot afford a long house-style book.",
                "genre": "test", "tone": "test",
                "length": "long", "style": "house",
            },
            timeout=20,
        )
        assert r.status_code == 402, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "neural credits" in detail or "credits" in detail

    def test_chimera_requires_two_distinct_bases(self, laureate_session):
        r = laureate_session.post(
            f"{BASE_URL}/api/books",
            json={
                "book_type": "novel",
                "prompt": "TEST chimera missing base styles.",
                "genre": "test", "tone": "test",
                "length": "short", "style": "chimera",
            },
            timeout=20,
        )
        assert r.status_code == 400
        assert "chimera" in (r.json().get("detail") or "").lower()


# ---------- laureate reads existing chimera book ----------


class TestLaureateReader:
    def test_get_whispering_light_book(self, laureate_session):
        r = laureate_session.get(f"{BASE_URL}/api/books/{LAUREATE_BOOK_ID}", timeout=15)
        if r.status_code == 404:
            pytest.skip("Whispering Light book id no longer exists; skipping")
        assert r.status_code == 200
        b = r.json()
        assert b["style"] == "chimera"
        assert b["status"] == "completed"
        assert b["has_cover_image"] is True
        assert b["illustrations_unlocked"] is True
        assert b["cover_image_url"] is not None
        assert "_id" not in b

    def test_chapters_have_illustrations(self, laureate_session):
        r = laureate_session.get(f"{BASE_URL}/api/books/{LAUREATE_BOOK_ID}/chapters", timeout=15)
        if r.status_code == 404:
            pytest.skip("book missing")
        assert r.status_code == 200
        chapters = r.json()
        assert len(chapters) >= 1
        for c in chapters:
            assert c["has_image"] is True
            assert c["image_url"] is not None
            assert c["image_url"].startswith("https://image.pollinations.ai/")

    def test_chapter_edit_no_tier_gate(self, laureate_session):
        r = laureate_session.get(f"{BASE_URL}/api/books/{LAUREATE_BOOK_ID}/chapters", timeout=15)
        if r.status_code == 404:
            pytest.skip("book missing")
        chapters = r.json()
        cid = chapters[0]["id"]
        original = chapters[0]["content"]
        r_edit = laureate_session.patch(
            f"{BASE_URL}/api/books/{LAUREATE_BOOK_ID}/chapters/{cid}",
            json={"content": original},
            timeout=20,
        )
        assert r_edit.status_code == 200


# ---------- payments (Stripe) — new checkout schema ----------


class TestPaymentsNewSchema:
    def test_subscription_checkout(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "subscription", "key": "wordsmith", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["checkout_url"].startswith("https://checkout.stripe.com/")

    def test_store_checkout(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "store", "key": "visual_prop", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://checkout.stripe.com/")

    def test_refill_checkout(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "refill", "key": "small", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"].startswith("https://checkout.stripe.com/")

    def test_checkout_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "refill", "key": "small", "origin_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 401

    def test_checkout_unknown_purpose(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "bogus", "key": "small", "origin_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 400

    def test_checkout_unknown_key(self, fresh_apprentice):
        r = fresh_apprentice["session"].post(
            f"{BASE_URL}/api/payments/checkout",
            json={"purpose": "refill", "key": "no_such_pack", "origin_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 400
