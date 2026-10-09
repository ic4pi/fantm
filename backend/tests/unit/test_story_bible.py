"""Story Bible inputs and reference tables reach generation.

Covers: the create form's bible fields and seed tables are stored before
generation starts, a bible PATCH only touches the fields it sends, and both
the outline and every chapter prompt actually carry the bible and tables.
"""
import asyncio

import pytest

import books
import generation
from conftest import cookies_for
from db import get_pool

SPORTS_BOOK = {
    "book_type": "novel",
    "prompt": "A washed-up coach takes a last-place hockey team to the finals",
    "title": "Blue Line",
    "length": "short",
    "style": "house",
    "setting": "Duluth, Minnesota, 1987",
    "backstory": "The Ironmen have not made the playoffs in eleven years.",
    "themes": ["redemption", " second chances "],
    "pov": "first_person",
    "style_notes": "Short punchy sentences in game scenes.",
    "influences": "Friday Night Lights",
    "tables": [
        {"name": "Opponents", "columns": ["Team", "Coach"], "rows": [{"Team": "Thunder Bay Wolves", "Coach": "Pete Laroche"}]},
        {"name": "Results", "columns": ["Game", "Opponent", "Score", "W/L"],
         "rows": [{"Game": "1", "Opponent": "Thunder Bay Wolves", "Score": "2-5", "W/L": "L"}]},
    ],
}


async def _make_user():
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into users (email, password_hash, name, credit_balance, last_stipend_at) values ($1,'h','U',100000,now()) returning id",
        f"sb_{id(object())}@fantm.ink",
    )
    return str(row["id"])


async def _get_book(book_id):
    pool = await get_pool()
    return dict(await pool.fetchrow("select * from books where id = $1", book_id))


async def _get_tables(book_id):
    pool = await get_pool()
    return [dict(r) for r in await pool.fetch("select * from book_tables where book_id = $1 order by created_at", book_id)]


@pytest.fixture
def user(db, monkeypatch):
    monkeypatch.setattr(books, "run_generation", lambda *a, **k: asyncio.sleep(0))
    uid = db.call(_make_user)
    return {"id": uid, "cookies": cookies_for(uid)}


def test_create_stores_the_bible_and_title(client, db, user):
    book_id = client.post("/api/books", json=SPORTS_BOOK, cookies=user["cookies"]).json()["id"]
    doc = db.call(_get_book, book_id)
    assert doc["title"] == "Blue Line"
    assert doc["bible"] == {
        "title": "Blue Line", "setting": "Duluth, Minnesota, 1987",
        "backstory": "The Ironmen have not made the playoffs in eleven years.",
        "themes": ["redemption", "second chances"], "pov": "first_person",
        "style_notes": "Short punchy sentences in game scenes.", "influences": "Friday Night Lights",
        "subject": "", "period": "",
    }


def test_create_stores_seed_tables_with_their_rows(client, db, user):
    book_id = client.post("/api/books", json=SPORTS_BOOK, cookies=user["cookies"]).json()["id"]
    tables = db.call(_get_tables, book_id)
    assert [t["name"] for t in tables] == ["Opponents", "Results"]
    assert tables[1]["rows"] == [{"Game": "1", "Opponent": "Thunder Bay Wolves", "Score": "2-5", "W/L": "L"}]


def test_too_many_seed_tables_is_rejected(client, user):
    body = SPORTS_BOOK | {"tables": [{"name": f"t{i}", "columns": ["a"]} for i in range(books.MAX_TABLES_PER_BOOK + 1)]}
    assert client.post("/api/books", json=body, cookies=user["cookies"]).status_code == 422


def test_unknown_pov_is_rejected(client, user):
    assert client.post("/api/books", json=SPORTS_BOOK | {"pov": "fourth_person"}, cookies=user["cookies"]).status_code == 422


def test_bible_patch_only_touches_sent_fields(client, db, user):
    book_id = client.post("/api/books", json=SPORTS_BOOK, cookies=user["cookies"]).json()["id"]
    r = client.patch(f"/api/books/{book_id}/bible", json={"pov": "third_limited"}, cookies=user["cookies"])
    assert r.status_code == 200
    bible = r.json()["bible"]
    assert bible["pov"] == "third_limited"
    assert bible["setting"] == "Duluth, Minnesota, 1987" and bible["title"] == "Blue Line"


def _capture_chat(monkeypatch, reply):
    sent = []

    def fake_chat(messages, **kwargs):
        sent.append(messages[-1]["content"])
        return reply
    monkeypatch.setattr(generation, "_chat", fake_chat)
    return sent


def test_outline_prompt_carries_bible_title_and_tables(monkeypatch):
    sent = _capture_chat(monkeypatch, '{"title": "AI Title", "chapters": []}')
    book = {"book_type": "novel", "genre": "sports", "tone": "gritty", "length": "short", "prompt": "p" * 20,
            "bible": {"title": "Blue Line", "setting": "Duluth, 1987", "pov": "first_person", "themes": ["redemption"]}}
    generation.generate_outline(book, SPORTS_BOOK["tables"])
    prompt = sent[0]
    assert 'titled this book "Blue Line"' in prompt
    assert "Setting: Duluth, 1987" in prompt and "first person" in prompt and "redemption" in prompt
    assert "Thunder Bay Wolves | 2-5 | L" in prompt


def test_chapter_prompt_carries_bible_and_tables(monkeypatch):
    sent = _capture_chat(monkeypatch, "prose")
    book = {"book_type": "novel", "genre": "sports", "tone": "gritty", "style": "house",
            "bible": {"setting": "Duluth, 1987", "style_notes": "Short punchy sentences."}}
    generation.generate_chapter_content(book, {"title": "Opener", "summary": "s"}, 0, 5, [], SPORTS_BOOK["tables"])
    prompt = sent[0]
    assert "Setting: Duluth, 1987" in prompt and "Short punchy sentences." in prompt
    assert "Pete Laroche" in prompt


def test_rendered_tables_are_capped(monkeypatch):
    big = [{"name": "Big", "columns": ["x"], "rows": [{"x": "y" * 100}] * 500}]
    text = generation._render_reference_tables(big)
    assert len(text) <= generation.MAX_TABLES_PROMPT_CHARS + 40 and text.endswith("[...tables truncated]")


def test_generation_keeps_the_authors_title(db, user, monkeypatch, client):
    monkeypatch.setattr(generation, "generate_outline", lambda bk, tables=None: {
        "title": "Some AI Title", "premise": "x", "characters": [], "plot_threads": [], "chapters": []})
    book_id = client.post("/api/books", json=SPORTS_BOOK, cookies=user["cookies"]).json()["id"]
    db.call(generation.run_generation, book_id)
    assert db.call(_get_book, book_id)["title"] == "Blue Line"
