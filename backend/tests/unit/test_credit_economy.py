"""Credits may only ever be spent through an atomic reservation.

The regression these cover: spending used to read the balance, decide the
user could afford it, then debit in a separate write. Concurrent requests
each passed their own check, so a user could drive the balance as negative
as they had parallel requests open.
"""
import asyncio

import pytest

import credits
from db import get_pool


async def _make_user(balance):
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into users (email, password_hash, name, credit_balance) values ($1,'h','U',$2) returning id",
        f"u_{id(object())}@fantm.ink", balance,
    )
    return str(row["id"])


async def _get_balance_via(user_id):
    return await credits.get_balance(user_id)


async def _reserve(user_id, amount, description="book"):
    return await credits.reserve_credits(user_id, amount, description)


async def _settle(user_id, reserved, actual, description="settled"):
    return await credits.settle_reservation(user_id, reserved, actual, description)


async def _release(user_id, amount, description="refunded"):
    return await credits.release_reservation(user_id, amount, description)


async def _one_tx(user_id):
    pool = await get_pool()
    return await pool.fetchrow("select * from credit_transactions where user_id = $1", user_id)


def test_reserve_refuses_when_balance_is_short(db):
    uid = db.call(_make_user, 100)
    assert db.call(_reserve, uid, 500) is None
    assert db.call(_get_balance_via, uid) == 100


def test_reserve_debits_when_affordable(db):
    uid = db.call(_make_user, 1000)
    assert db.call(_reserve, uid, 400) == 600


async def _make_book(user_id):
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into books (user_id, book_type, length, prompt) values ($1,'novel','short',$2) returning id",
        user_id, "p" * 20,
    )
    return str(row["id"])


def test_reserve_writes_a_hold_to_the_ledger(db):
    async def go():
        uid = await _make_user(1000)
        book_id = await _make_book(uid)
        await credits.reserve_credits(uid, 400, "book", related_book_id=book_id)
        tx = await _one_tx(uid)
        return tx, book_id

    tx, book_id = db.call(go)
    assert (tx["type"], tx["amount"], tx["balance_after"], str(tx["related_book_id"])) == ("hold", -400, 600, book_id)


def test_concurrent_reservations_cannot_overdraw(db):
    async def go():
        uid = await _make_user(1000)
        results = await asyncio.gather(*[credits.reserve_credits(uid, 400, "book") for _ in range(10)])
        return uid, results

    uid, results = db.call(go)
    granted = [r for r in results if r is not None]
    assert len(granted) == 2
    assert db.call(_get_balance_via, uid) == 200


def test_settle_refunds_the_unused_remainder(db):
    async def go():
        uid = await _make_user(1000)
        await credits.reserve_credits(uid, 400, "book")
        await credits.settle_reservation(uid, reserved=400, actual=250, description="settled")
        return uid

    uid = db.call(go)
    assert db.call(_get_balance_via, uid) == 750


def test_settle_collects_an_overage(db):
    async def go():
        uid = await _make_user(1000)
        await credits.reserve_credits(uid, 400, "book")
        await credits.settle_reservation(uid, reserved=400, actual=500, description="settled")
        return uid

    uid = db.call(go)
    assert db.call(_get_balance_via, uid) == 500


def test_settle_caps_an_overage_at_the_balance(db):
    """A shortfall past the estimate is ours to absorb, not the user's to owe."""
    async def go():
        uid = await _make_user(450)
        await credits.reserve_credits(uid, 400, "book")
        await credits.settle_reservation(uid, reserved=400, actual=900, description="settled")
        return uid

    uid = db.call(go)
    assert db.call(_get_balance_via, uid) == 0


def test_settle_on_an_exact_estimate_moves_nothing(db):
    async def go():
        uid = await _make_user(1000)
        await credits.reserve_credits(uid, 400, "book")
        await credits.settle_reservation(uid, reserved=400, actual=400, description="settled")
        return uid

    uid = db.call(go)
    assert db.call(_get_balance_via, uid) == 600


def test_release_returns_an_unconsumed_reservation(db):
    async def go():
        uid = await _make_user(1000)
        await credits.reserve_credits(uid, 400, "book")
        await credits.release_reservation(uid, 400, "refunded")
        return uid

    uid = db.call(go)
    assert db.call(_get_balance_via, uid) == 1000


@pytest.mark.parametrize("amount", [0, -50])
def test_reserving_nothing_is_a_noop(db, amount):
    uid = db.call(_make_user, 1000)
    assert db.call(_reserve, uid, amount) == 1000
    assert db.call(_get_balance_via, uid) == 1000
