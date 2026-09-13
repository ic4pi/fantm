"""Book creation holds credits up front; generation reconciles the hold.

Covers the end-to-end money path: reserve on POST /api/books, settle against
real word counts when generation ends, and never charge for a PDF that
failed to render.
"""
import asyncio
import threading

import pytest

import books
import credits
import generation
import pricing
from conftest import cookies_for
from db import get_pool

BOOK_BODY = {"book_type": "novel", "prompt": "a lighthouse keeper who cannot sleep",
             "length": "short", "style": "house"}
START_BALANCE = 10000


def estimate():
    return pricing.estimate_word_cost(books.LENGTH_CHAPTERS["short"], pricing.style_multiplier("house"))


async def _make_user(balance=START_BALANCE):
    pool = await get_pool()
    # last_stipend_at is set to now — otherwise ensure_monthly_stipend (called
    # at the top of create_book) sees a NULL and grants a surprise stipend on
    # top of the seeded balance before the test even gets to its assertion.
    row = await pool.fetchrow(
        "insert into users (email, password_hash, name, credit_balance, last_stipend_at) values ($1,'h','U',$2,now()) returning id",
        f"u_{id(object())}@fantm.ink", balance,
    )
    return str(row["id"])


async def _set_balance(user_id, amount):
    pool = await get_pool()
    await pool.execute("update users set credit_balance = $2 where id = $1", user_id, amount)


async def _one_tx_of_type(tx_type):
    pool = await get_pool()
    return await pool.fetchrow("select * from credit_transactions where type = $1", tx_type)


async def _get_book(book_id):
    pool = await get_pool()
    return dict(await pool.fetchrow("select * from books where id = $1", book_id))


async def _count_books():
    pool = await get_pool()
    return await pool.fetchval("select count(*) from books")


async def _count_refunds():
    pool = await get_pool()
    return await pool.fetchval("select count(*) from credit_transactions where type = 'refund'")


@pytest.fixture
def user(db, monkeypatch):
    monkeypatch.setattr(books, "run_generation", lambda *a, **k: asyncio.sleep(0))
    uid = db.call(_make_user, START_BALANCE)
    return {"id": uid, "cookies": cookies_for(uid)}


def test_creating_a_book_debits_the_estimate_up_front(client, db, user):
    assert client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code == 200
    assert db.call(credits.get_balance, user["id"]) == START_BALANCE - estimate()


def test_the_hold_is_recorded_against_the_book(client, db, user):
    book_id = client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).json()["id"]
    tx = db.call(_one_tx_of_type, "hold")
    assert str(tx["related_book_id"]) == book_id and tx["amount"] == -estimate()


def test_the_book_records_its_reservation_for_settlement(client, db, user):
    book_id = client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).json()["id"]
    doc = db.call(_get_book, book_id)
    assert doc["reserved_nc"] == estimate() and doc["settled"] is False


def test_repeated_creates_cannot_drive_the_balance_negative(client, db, user):
    cost = estimate()
    statuses = [client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code for _ in range(12)]
    assert statuses.count(200) == START_BALANCE // cost
    assert set(statuses) <= {200, 402}
    assert db.call(credits.get_balance, user["id"]) >= 0


def test_a_refused_reservation_leaves_no_orphan_book(client, db, user):
    db.call(_set_balance, user["id"], estimate() - 1)
    assert client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code == 402
    assert db.call(_count_books) == 0


# ---------- settlement ----------

RESERVED = 5000


@pytest.fixture
def pending_book(db, monkeypatch):
    monkeypatch.setattr(generation, "generate_outline", lambda bk: {
        "title": "The Sleepless Keeper", "premise": "A premise.", "characters": [], "plot_threads": [],
        "chapters": [{"title": "One", "summary": "s"}, {"title": "Two", "summary": "s"}],
    })
    monkeypatch.setattr(generation, "update_story_state", lambda *a, **k: {
        "running_summary": "s", "characters": [], "plot_threads": []})

    async def setup():
        pool = await get_pool()
        u = await pool.fetchrow(
            "insert into users (email, password_hash, name, credit_balance) values ($1,'h','G',$2) returning id",
            f"g_{id(object())}@fantm.ink", START_BALANCE - RESERVED,
        )
        b = await pool.fetchrow(
            """insert into books (user_id, title, book_type, length, prompt, style,
                 total_chapters, status, reserved_nc, settled)
               values ($1,'Generating...','novel','short',$2,'house',2,'pending',$3,false)
               returning id""",
            u["id"], "p" * 20, RESERVED,
        )
        return {"user_id": str(u["id"]), "book_id": str(b["id"])}

    return db.call(setup)


def test_an_under_estimate_book_refunds_the_difference(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 300)
    db.call(generation.run_generation, pending_book["book_id"])
    doc = db.call(_get_book, pending_book["book_id"])
    assert doc["status"] == "completed" and doc["settled"] is True and doc["burned_nc"] == 600
    assert db.call(credits.get_balance, pending_book["user_id"]) == START_BALANCE - 600


def test_a_failed_generation_only_charges_for_what_it_wrote(db, pending_book, monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("provider died")
        return "word " * 300

    monkeypatch.setattr(generation, "generate_chapter_content", flaky)
    db.call(generation.run_generation, pending_book["book_id"])
    doc = db.call(_get_book, pending_book["book_id"])
    assert doc["status"] == "failed" and doc["burned_nc"] == 300
    assert db.call(credits.get_balance, pending_book["user_id"]) == START_BALANCE - 300


def test_a_book_that_never_started_is_refunded_in_full(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_outline",
                         lambda bk: (_ for _ in ()).throw(RuntimeError("groq down")))
    db.call(generation.run_generation, pending_book["book_id"])
    assert db.call(_get_book, pending_book["book_id"])["status"] == "failed"
    assert db.call(credits.get_balance, pending_book["user_id"]) == START_BALANCE


def test_settlement_runs_exactly_once(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 300)
    db.call(generation.run_generation, pending_book["book_id"])
    db.call(generation.run_generation, pending_book["book_id"])
    assert db.call(_count_refunds) == 1


def test_an_overrun_never_pushes_the_balance_negative(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 9000)
    db.call(_set_balance, pending_book["user_id"], 0)
    db.call(generation.run_generation, pending_book["book_id"])
    assert db.call(credits.get_balance, pending_book["user_id"]) == 0


# ---------- PDF export ----------

@pytest.fixture
def completed_book(db, user):
    async def setup():
        pool = await get_pool()
        b = await pool.fetchrow(
            """insert into books (user_id, title, book_type, length, prompt, status, pdf_unlocked, illustrations_unlocked)
               values ($1,'Done Book','novel','short',$2,'completed',false,false) returning id""",
            user["id"], "p" * 20,
        )
        await pool.execute(
            """insert into chapters (book_id, index, title, content, word_count, status)
               values ($1,0,'One','Some prose.',2,'done')""",
            b["id"],
        )
        return str(b["id"])

    return {**user, "book_id": db.call(setup)}


def test_a_failed_render_charges_nothing(client, db, completed_book, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("reportlab exploded")

    monkeypatch.setattr(books, "build_book_pdf", boom)
    before = db.call(credits.get_balance, completed_book["id"])
    assert client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"]).status_code == 500
    assert db.call(credits.get_balance, completed_book["id"]) == before
    assert not db.call(_get_book, completed_book["book_id"]).get("pdf_unlocked")


def test_the_pdf_build_runs_off_the_event_loop(client, completed_book, monkeypatch):
    seen = {}

    def record(book, chapters):
        seen["thread"] = threading.current_thread().name
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(books, "build_book_pdf", record)
    r = client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    assert r.status_code == 200 and r.content == b"%PDF-1.4 fake"
    assert "MainThread" not in seen["thread"]


def test_a_successful_export_charges_once(client, db, completed_book, monkeypatch):
    monkeypatch.setattr(books, "build_book_pdf", lambda b, c: b"%PDF-1.4 fake")
    start = db.call(credits.get_balance, completed_book["id"])
    client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    after_first = db.call(credits.get_balance, completed_book["id"])
    assert start - after_first == pricing.PDF_EXPORT_COST
    client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    assert db.call(credits.get_balance, completed_book["id"]) == after_first


def test_export_is_refused_without_the_credits(client, db, completed_book, monkeypatch):
    monkeypatch.setattr(books, "build_book_pdf", lambda b, c: b"%PDF")
    db.call(_set_balance, completed_book["id"], 1)
    assert client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"]).status_code == 402
    assert db.call(credits.get_balance, completed_book["id"]) == 1
