"""Every id-addressed route must be scoped to the caller who owns the record.

The regression these cover: PATCH chapter scoped its *write* to the book id but
read the chapter back by id alone, so naming your own book plus someone else's
chapter id returned their prose. Separately, a malformed id reached
bson.ObjectId() directly and surfaced as a 500 rather than a 404.
"""
import pytest
from bson import ObjectId

from conftest import cookies_for, run


@pytest.fixture
def people(db):
    async def setup():
        alice = await db.users.insert_one({"email": "alice@fantm.ink", "name": "Alice", "tier": "laureate", "credit_balance": 99999})
        bob = await db.users.insert_one({"email": "bob@fantm.ink", "name": "Bob", "tier": "laureate", "credit_balance": 99999})
        bob_book = await db.books.insert_one({
            "user_id": str(bob.inserted_id), "title": "Bob's Book", "book_type": "novel",
            "length": "short", "prompt": "p" * 20, "status": "completed", "illustrations_unlocked": False,
        })
        bob_chapter = await db.chapters.insert_one({
            "book_id": str(bob_book.inserted_id), "index": 0, "title": "Secret",
            "content": "BOBS PRIVATE PROSE", "word_count": 3, "status": "done",
        })
        alice_book = await db.books.insert_one({
            "user_id": str(alice.inserted_id), "title": "Alice's Book", "book_type": "novel",
            "length": "short", "prompt": "p" * 20, "status": "completed", "illustrations_unlocked": False,
        })
        return {
            "alice": str(alice.inserted_id), "bob": str(bob.inserted_id),
            "alice_book": str(alice_book.inserted_id),
            "bob_book": str(bob_book.inserted_id), "bob_chapter": str(bob_chapter.inserted_id),
        }
    return run(setup())


def test_patch_cannot_read_a_chapter_of_someone_elses_book(client, people):
    r = client.patch(
        f"/api/books/{people['alice_book']}/chapters/{people['bob_chapter']}",
        json={"content": "overwritten"}, cookies=cookies_for(people["alice"], "alice@fantm.ink"),
    )
    assert r.status_code == 404
    assert "BOBS PRIVATE PROSE" not in r.text


def test_patch_does_not_modify_a_chapter_of_someone_elses_book(client, db, people):
    client.patch(
        f"/api/books/{people['alice_book']}/chapters/{people['bob_chapter']}",
        json={"content": "overwritten"}, cookies=cookies_for(people["alice"], "alice@fantm.ink"),
    )
    chapter = run(db.chapters.find_one({"_id": ObjectId(people["bob_chapter"])}))
    assert chapter["content"] == "BOBS PRIVATE PROSE"


def test_owner_can_still_edit_their_own_chapter(client, people):
    r = client.patch(
        f"/api/books/{people['bob_book']}/chapters/{people['bob_chapter']}",
        json={"content": "a new draft entirely"}, cookies=cookies_for(people["bob"], "bob@fantm.ink"),
    )
    assert r.status_code == 200
    assert r.json()["content"] == "a new draft entirely"
    assert r.json()["word_count"] == 4


@pytest.mark.parametrize("path", ["/api/books/{id}", "/api/books/{id}/chapters"])
def test_cannot_read_someone_elses_book(client, people, path):
    r = client.get(path.format(id=people["bob_book"]), cookies=cookies_for(people["alice"], "alice@fantm.ink"))
    assert r.status_code == 404


def test_cannot_delete_someone_elses_book(client, db, people):
    r = client.delete(f"/api/books/{people['bob_book']}", cookies=cookies_for(people["alice"], "alice@fantm.ink"))
    assert r.status_code == 404
    assert run(db.books.count_documents({"_id": ObjectId(people["bob_book"])})) == 1


@pytest.mark.parametrize("bad", ["not-an-id", "123", "zzzzzzzzzzzzzzzzzzzzzzzz"])
def test_malformed_book_id_is_404_not_500(client, people, bad):
    r = client.get(f"/api/books/{bad}", cookies=cookies_for(people["alice"], "alice@fantm.ink"))
    assert r.status_code == 404


def test_malformed_chapter_id_is_404_not_500(client, people):
    r = client.patch(
        f"/api/books/{people['alice_book']}/chapters/nope", json={"content": "x"},
        cookies=cookies_for(people["alice"], "alice@fantm.ink"),
    )
    assert r.status_code == 404


def test_token_with_a_malformed_subject_is_rejected(client):
    import auth
    r = client.get("/api/books", cookies={"access_token": auth.create_access_token("not-an-object-id", "a@b.c")})
    assert r.status_code == 401


# --- payment status settles transactions, so it must not be world-readable ---

@pytest.fixture
def payment(db, people, monkeypatch):
    # The status route reconciles an unpaid session against Stripe. Stub the
    # lookup so the suite stays offline; the reconciliation itself is Stripe's
    # contract, not what these access-control tests are asserting.
    import stripe

    def unreachable(*a, **k):
        raise stripe.error.APIConnectionError("offline test")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", unreachable)

    async def setup():
        await db.payment_transactions.insert_one({
            "session_id": "cs_test_secret123", "user_id": people["bob"], "purpose": "store",
            "key": "writer_pack", "status": "initiated", "payment_status": "pending",
            "amount": 20.0, "currency": "usd",
        })
        return people
    return run(setup())


def test_payment_status_requires_authentication(client, payment):
    assert client.get("/api/payments/status/cs_test_secret123").status_code == 401


def test_payment_status_is_scoped_to_its_owner(client, payment):
    r = client.get("/api/payments/status/cs_test_secret123", cookies=cookies_for(payment["alice"], "alice@fantm.ink"))
    assert r.status_code == 404


def test_payment_status_is_readable_by_its_owner(client, payment):
    r = client.get("/api/payments/status/cs_test_secret123", cookies=cookies_for(payment["bob"], "bob@fantm.ink"))
    assert r.status_code == 200
    assert r.json()["session_id"] == "cs_test_secret123"
