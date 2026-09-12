"""Book creation holds credits up front; generation reconciles the hold.

Covers the end-to-end money path: reserve on POST /api/books, settle against
real word counts when generation ends, and never charge for a PDF that failed
to render.
"""
import asyncio
import threading
from datetime import datetime, timezone

import pytest
from bson import ObjectId

import books
import credits
import generation
import pricing
from conftest import cookies_for, run

BOOK_BODY = {"book_type": "novel", "prompt": "a lighthouse keeper who cannot sleep",
             "length": "short", "style": "house"}
START_BALANCE = 10000


def estimate():
    return pricing.estimate_word_cost(books.LENGTH_CHAPTERS["short"], pricing.style_multiplier("house"))


@pytest.fixture
def user(db, monkeypatch):
    monkeypatch.setattr(books, "run_generation", lambda *a, **k: asyncio.sleep(0))

    async def setup():
        res = await db.users.insert_one({
            "email": "u@fantm.ink", "name": "U", "tier": "apprentice",
            "credit_balance": START_BALANCE, "last_stipend_at": datetime.now(timezone.utc),
        })
        return str(res.inserted_id)

    uid = run(setup())
    return {"id": uid, "cookies": cookies_for(uid)}


def test_creating_a_book_debits_the_estimate_up_front(client, user):
    assert client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code == 200
    assert run(credits.get_balance(user["id"])) == START_BALANCE - estimate()


def test_the_hold_is_recorded_against_the_book(client, db, user):
    book_id = client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).json()["id"]
    tx = run(db.credit_transactions.find_one({"type": "hold"}))
    assert tx["related_book_id"] == book_id and tx["amount"] == -estimate()


def test_the_book_records_its_reservation_for_settlement(client, db, user):
    book_id = client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).json()["id"]
    doc = run(db.books.find_one({"_id": ObjectId(book_id)}))
    assert doc["reserved_nc"] == estimate() and doc["settled"] is False


def test_repeated_creates_cannot_drive_the_balance_negative(client, user):
    cost = estimate()
    statuses = [client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code for _ in range(12)]
    assert statuses.count(200) == START_BALANCE // cost
    assert set(statuses) <= {200, 402}
    assert run(credits.get_balance(user["id"])) >= 0


def test_a_refused_reservation_leaves_no_orphan_book(client, db, user):
    run(db.users.update_one({"_id": ObjectId(user["id"])}, {"$set": {"credit_balance": estimate() - 1}}))
    assert client.post("/api/books", json=BOOK_BODY, cookies=user["cookies"]).status_code == 402
    assert run(db.books.count_documents({})) == 0


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
        u = await db.users.insert_one({"email": "g@fantm.ink", "credit_balance": START_BALANCE - RESERVED, "tier": "apprentice"})
        b = await db.books.insert_one({
            "user_id": str(u.inserted_id), "title": "Generating...", "book_type": "novel",
            "genre": "", "tone": "", "length": "short", "prompt": "p" * 20, "style": "house",
            "premise": "", "characters": [], "plot_threads": [], "running_summary": "", "outline": [],
            "total_chapters": 2, "current_chapter": 0, "status": "pending",
            "reserved_nc": RESERVED, "settled": False,
        })
        return {"user_id": str(u.inserted_id), "book_id": str(b.inserted_id)}

    return run(setup())


def test_an_under_estimate_book_refunds_the_difference(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 300)
    run(generation.run_generation(pending_book["book_id"], db))
    doc = run(db.books.find_one({"_id": ObjectId(pending_book["book_id"])}))
    assert doc["status"] == "completed" and doc["settled"] is True and doc["burned_nc"] == 600
    assert run(credits.get_balance(pending_book["user_id"])) == START_BALANCE - 600


def test_a_failed_generation_only_charges_for_what_it_wrote(db, pending_book, monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("provider died")
        return "word " * 300

    monkeypatch.setattr(generation, "generate_chapter_content", flaky)
    run(generation.run_generation(pending_book["book_id"], db))
    doc = run(db.books.find_one({"_id": ObjectId(pending_book["book_id"])}))
    assert doc["status"] == "failed" and doc["burned_nc"] == 300
    assert run(credits.get_balance(pending_book["user_id"])) == START_BALANCE - 300


def test_a_book_that_never_started_is_refunded_in_full(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_outline",
                        lambda bk: (_ for _ in ()).throw(RuntimeError("groq down")))
    run(generation.run_generation(pending_book["book_id"], db))
    assert run(db.books.find_one({"_id": ObjectId(pending_book["book_id"])}))["status"] == "failed"
    assert run(credits.get_balance(pending_book["user_id"])) == START_BALANCE


def test_settlement_runs_exactly_once(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 300)
    run(generation.run_generation(pending_book["book_id"], db))
    run(generation.run_generation(pending_book["book_id"], db))
    assert run(db.credit_transactions.count_documents({"type": "refund"})) == 1


def test_an_overrun_never_pushes_the_balance_negative(db, pending_book, monkeypatch):
    monkeypatch.setattr(generation, "generate_chapter_content", lambda *a, **k: "word " * 9000)
    run(db.users.update_one({"_id": ObjectId(pending_book["user_id"])}, {"$set": {"credit_balance": 0}}))
    run(generation.run_generation(pending_book["book_id"], db))
    assert run(credits.get_balance(pending_book["user_id"])) == 0


# ---------- PDF export ----------

@pytest.fixture
def completed_book(db, user):
    async def setup():
        res = await db.books.insert_one({
            "user_id": user["id"], "title": "Done Book", "book_type": "novel", "length": "short",
            "prompt": "p" * 20, "status": "completed", "pdf_unlocked": False, "illustrations_unlocked": False,
        })
        await db.chapters.insert_one({"book_id": str(res.inserted_id), "index": 0, "title": "One",
                                      "content": "Some prose.", "word_count": 2, "status": "done"})
        return str(res.inserted_id)

    return {**user, "book_id": run(setup())}


def test_a_failed_render_charges_nothing(client, db, completed_book, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("reportlab exploded")

    monkeypatch.setattr(books, "build_book_pdf", boom)
    before = run(credits.get_balance(completed_book["id"]))
    assert client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"]).status_code == 500
    assert run(credits.get_balance(completed_book["id"])) == before
    assert not run(db.books.find_one({"_id": ObjectId(completed_book["book_id"])})).get("pdf_unlocked")


def test_the_pdf_build_runs_off_the_event_loop(client, completed_book, monkeypatch):
    seen = {}

    def record(book, chapters):
        seen["thread"] = threading.current_thread().name
        return b"%PDF-1.4 fake"

    monkeypatch.setattr(books, "build_book_pdf", record)
    r = client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    assert r.status_code == 200 and r.content == b"%PDF-1.4 fake"
    assert "MainThread" not in seen["thread"]


def test_a_successful_export_charges_once(client, completed_book, monkeypatch):
    monkeypatch.setattr(books, "build_book_pdf", lambda b, c: b"%PDF-1.4 fake")
    start = run(credits.get_balance(completed_book["id"]))
    client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    after_first = run(credits.get_balance(completed_book["id"]))
    assert start - after_first == pricing.PDF_EXPORT_COST
    client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"])
    assert run(credits.get_balance(completed_book["id"])) == after_first


def test_export_is_refused_without_the_credits(client, completed_book, monkeypatch):
    monkeypatch.setattr(books, "build_book_pdf", lambda b, c: b"%PDF")
    run(db_set_balance(completed_book["id"], 1))
    assert client.get(f"/api/books/{completed_book['book_id']}/pdf", cookies=completed_book["cookies"]).status_code == 402
    assert run(credits.get_balance(completed_book["id"])) == 1


async def db_set_balance(user_id, amount):
    await credits.db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"credit_balance": amount}})
