"""Credits may only ever be spent through an atomic reservation.

The regression these cover: spending used to read the balance, decide the user
could afford it, then debit in a separate write. Concurrent requests each
passed their own check, so a user could drive the balance as negative as they
had parallel requests open.
"""
import asyncio

import pytest

import credits
from conftest import run


async def _user(db, balance):
    res = await db.users.insert_one({"email": "u@fantm.ink", "credit_balance": balance, "tier": "apprentice"})
    return str(res.inserted_id)


def test_reserve_refuses_when_balance_is_short(db):
    uid = run(_user(db, 100))
    assert run(credits.reserve_credits(uid, 500, "book")) is None
    assert run(credits.get_balance(uid)) == 100


def test_reserve_debits_when_affordable(db):
    uid = run(_user(db, 1000))
    assert run(credits.reserve_credits(uid, 400, "book")) == 600


def test_reserve_writes_a_hold_to_the_ledger(db):
    uid = run(_user(db, 1000))
    run(credits.reserve_credits(uid, 400, "book", related_book_id="b1"))
    tx = run(db.credit_transactions.find_one({"user_id": uid}))
    assert (tx["type"], tx["amount"], tx["balance_after"], tx["related_book_id"]) == ("hold", -400, 600, "b1")


def test_concurrent_reservations_cannot_overdraw(db):
    uid = run(_user(db, 1000))

    async def race():
        return await asyncio.gather(*[credits.reserve_credits(uid, 400, "book") for _ in range(10)])

    granted = [r for r in run(race()) if r is not None]
    assert len(granted) == 2
    assert run(credits.get_balance(uid)) == 200


def test_settle_refunds_the_unused_remainder(db):
    uid = run(_user(db, 1000))
    run(credits.reserve_credits(uid, 400, "book"))
    run(credits.settle_reservation(uid, reserved=400, actual=250, description="settled"))
    assert run(credits.get_balance(uid)) == 750


def test_settle_collects_an_overage(db):
    uid = run(_user(db, 1000))
    run(credits.reserve_credits(uid, 400, "book"))
    run(credits.settle_reservation(uid, reserved=400, actual=500, description="settled"))
    assert run(credits.get_balance(uid)) == 500


def test_settle_caps_an_overage_at_the_balance(db):
    """A shortfall past the estimate is ours to absorb, not the user's to owe."""
    uid = run(_user(db, 450))
    run(credits.reserve_credits(uid, 400, "book"))
    run(credits.settle_reservation(uid, reserved=400, actual=900, description="settled"))
    assert run(credits.get_balance(uid)) == 0


def test_settle_on_an_exact_estimate_moves_nothing(db):
    uid = run(_user(db, 1000))
    run(credits.reserve_credits(uid, 400, "book"))
    run(credits.settle_reservation(uid, reserved=400, actual=400, description="settled"))
    assert run(credits.get_balance(uid)) == 600


def test_release_returns_an_unconsumed_reservation(db):
    uid = run(_user(db, 1000))
    run(credits.reserve_credits(uid, 400, "book"))
    run(credits.release_reservation(uid, 400, "refunded"))
    assert run(credits.get_balance(uid)) == 1000


@pytest.mark.parametrize("amount", [0, -50])
def test_reserving_nothing_is_a_noop(db, amount):
    uid = run(_user(db, 1000))
    assert run(credits.reserve_credits(uid, amount, "book")) == 1000
    assert run(credits.get_balance(uid)) == 1000
