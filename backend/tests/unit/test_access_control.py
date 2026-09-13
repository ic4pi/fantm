"""Every id-addressed route must be scoped to the caller who owns the record.

The regression these cover: PATCH chapter scoped its write to the book id
but read the chapter back by id alone, so naming your own book plus another
user's chapter id returned their prose; it is now a single scoped
find_one_and_update-equivalent. GET /api/payments/status took no
authentication at all despite granting credits. Malformed ids reached the
database driver directly and surfaced as 500s.
"""
import pytest

from conftest import cookies_for
from db import get_pool


async def _seed_people():
    pool = await get_pool()
    alice = await pool.fetchrow(
        "insert into users (email, password_hash, name, tier, credit_balance) values ($1,'h','Alice','laureate',99999) returning id",
        "alice@fantm.ink",
    )
    bob = await pool.fetchrow(
        "insert into users (email, password_hash, name, tier, credit_balance) values ($1,'h','Bob','laureate',99999) returning id",
        "bob@fantm.ink",
    )
    bob_book = await pool.fetchrow(
        """insert into books (user_id, title, book_type, length, prompt, status, illustrations_unlocked)
           values ($1,'Bob''s Book','novel','short',$2,'completed',false) returning id""",
        bob["id"], "p" * 20,
    )
    bob_chapter = await pool.fetchrow(
        """insert into chapters (book_id, index, title, content, word_count, status)
           values ($1,0,'Secret','BOBS PRIVATE PROSE',3,'done') returning id""",
        bob_book["id"],
    )
    alice_book = await pool.fetchrow(
        """insert into books (user_id, title, book_type, length, prompt, status, illustrations_unlocked)
           values ($1,'Alice''s Book','novel','short',$2,'completed',false) returning id""",
        alice["id"], "p" * 20,
    )
    return {
        "alice": str(alice["id"]), "bob": str(bob["id"]),
        "alice_book": str(alice_book["id"]),
        "bob_book": str(bob_book["id"]), "bob_chapter": str(bob_chapter["id"]),
    }


async def _get_chapter_content(chapter_id):
    pool = await get_pool()
    row = await pool.fetchrow("select content from chapters where id = $1", chapter_id)
    return row["content"]


async def _seed_payment(bob_id):
    pool = await get_pool()
    await pool.execute(
        """insert into payment_transactions (session_id, user_id, purpose, key, lookup_key, amount, currency, status, payment_status)
           values ('cs_test_secret123',$1,'store','writer_pack','store_writer_pack',20.0,'usd','initiated','pending')""",
        bob_id,
    )


@pytest.fixture
def people(db):
    return db.call(_seed_people)


@pytest.fixture
def payment(db, people):
    db.call(_seed_payment, people["bob"])
    return people


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
    assert db.call(_get_chapter_content, people["bob_chapter"]) == "BOBS PRIVATE PROSE"


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

    async def still_there():
        pool = await get_pool()
        return await pool.fetchval("select count(*) from books where id = $1", people["bob_book"])

    assert db.call(still_there) == 1


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
    r = client.get("/api/books", cookies={"access_token": auth.create_access_token("not-a-uuid", "a@b.c")})
    assert r.status_code == 401


# --- payment status settles transactions, so it must not be world-readable ---

def test_payment_status_requires_authentication(client, payment):
    assert client.get("/api/payments/status/cs_test_secret123").status_code == 401


def test_payment_status_is_scoped_to_its_owner(client, payment):
    r = client.get("/api/payments/status/cs_test_secret123", cookies=cookies_for(payment["alice"], "alice@fantm.ink"))
    assert r.status_code == 404


def test_payment_status_is_readable_by_its_owner(client, payment, monkeypatch):
    import stripe

    def unreachable(*a, **k):
        raise stripe.error.APIConnectionError("offline test")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", unreachable)
    r = client.get("/api/payments/status/cs_test_secret123", cookies=cookies_for(payment["bob"], "bob@fantm.ink"))
    assert r.status_code == 200
    assert r.json()["session_id"] == "cs_test_secret123"
