"""Document import: read .txt/.md/.docx/.pdf, extract create-form fields,
merge chunked results within the form's limits."""
import io
import json
import zipfile

import pytest

import importer
from conftest import cookies_for
from db import get_pool

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(paragraphs, table_rows=()):
    p = "".join(f'<w:p><w:r><w:t>{t}</w:t></w:r></w:p>' for t in paragraphs)
    rows = "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in r) + "</w:tr>"
        for r in table_rows
    )
    tbl = f"<w:tbl>{rows}</w:tbl>" if table_rows else ""
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{p}{tbl}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def _pdf(text):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


def test_reads_plain_text_and_markdown():
    assert importer.read_document("notes.md", b"# Blue Line\n\n\n\nSetting: Duluth") == "# Blue Line\n\nSetting: Duluth"


def test_reads_docx_paragraphs_and_tables():
    text = importer.read_document("bible.docx", _docx(["Setting: Duluth"], [["Game", "Score"], ["1", "2-5"]]))
    assert "Setting: Duluth" in text and "Game | Score" in text and "1 | 2-5" in text


def test_reads_pdf_text():
    assert "Coach Laroche" in importer.read_document("bible.pdf", _pdf("Coach Laroche runs the bench"))


@pytest.mark.parametrize("name,data", [("x.rtf", b"hi"), ("x.docx", b"not a zip"), ("x.txt", b"   ")])
def test_unreadable_documents_are_refused_with_a_reason(name, data):
    with pytest.raises(importer.UnreadableDocument):
        importer.read_document(name, data)


def test_merge_combines_parts_and_dedupes():
    merged = importer.merge_extractions([
        {"title": "Blue Line", "setting": "Duluth", "themes": ["Redemption"],
         "characters": [{"name": "Jake", "role": "", "description": ""}],
         "tables": [{"name": "Results", "columns": ["Game", "Score"], "rows": [{"Game": "1", "Score": "2-5"}]}]},
        {"title": "Other", "setting": "1987", "themes": ["redemption", "loyalty"],
         "characters": [{"name": "jake", "role": "goalie", "description": "nervous"}],
         "tables": [{"name": "results", "columns": ["Score", "W/L"], "rows": [{"Game": "2", "Score": "4-3", "W/L": "W"}]}]},
    ])
    assert merged["title"] == "Blue Line"
    assert merged["setting"] == "Duluth\n\n1987"
    assert merged["themes"] == ["Redemption", "loyalty"]
    assert merged["characters"] == [{"name": "Jake", "role": "goalie", "description": "nervous"}]
    assert merged["tables"] == [{"name": "Results", "columns": ["Game", "Score", "W/L"],
                                 "rows": [{"Game": "1", "Score": "2-5"}, {"Game": "2", "Score": "4-3", "W/L": "W"}]}]


def test_merge_drops_invalid_choices_and_clamps_to_form_limits():
    merged = importer.merge_extractions([{
        "book_type": "screenplay", "pov": "fourth", "prompt": "p" * 5000,
        "themes": [f"t{i}" for i in range(40)], "characters": [{"name": f"c{i}"} for i in range(20)],
    }])
    assert merged["book_type"] == "" and merged["pov"] == ""
    assert len(merged["prompt"]) == 4000 and len(merged["themes"]) == 15 and len(merged["characters"]) == 12


def test_missing_fields_come_back_empty_not_invented():
    merged = importer.merge_extractions([{}])
    assert merged["setting"] == "" and merged["characters"] == [] and merged["tables"] == []


# ---------- endpoint ----------

async def _make_user():
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into users (email, password_hash, name, credit_balance, last_stipend_at) values ($1,'h','U',0,now()) returning id",
        f"imp_{id(object())}@fantm.ink",
    )
    return str(row["id"])


@pytest.fixture
def user(db):
    uid = db.call(_make_user)
    return {"id": uid, "cookies": cookies_for(uid)}


def test_extract_endpoint_returns_reviewable_fields(client, user, monkeypatch):
    sent = []

    def fake_chat(messages, **kwargs):
        sent.append(messages[-1]["content"])
        return json.dumps({"title": "Blue Line", "setting": "Duluth, 1987",
                           "characters": [{"name": "Jake", "role": "goalie", "description": ""}]})
    monkeypatch.setattr(importer, "_chat", fake_chat)
    r = client.post("/api/books/extract", files={"file": ("bible.docx", _docx(["Setting: Duluth, 1987"]))}, cookies=user["cookies"])
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Blue Line" and body["characters"][0]["name"] == "Jake"
    assert body["chars_read"] == body["chars_total"]
    assert "Setting: Duluth, 1987" in sent[0]


def test_long_documents_are_read_in_parts_up_to_a_cap(client, user, monkeypatch):
    calls = []
    monkeypatch.setattr(importer, "_chat", lambda messages, **k: calls.append(1) or "{}")
    text = ("x" * 999 + "\n") * 60  # 60,000 chars
    r = client.post("/api/books/extract", files={"file": ("long.txt", text.encode())}, cookies=user["cookies"])
    assert len(calls) == importer.MAX_CHUNKS
    assert r.json()["chars_read"] == importer.MAX_CHUNKS * importer.CHUNK_CHARS < r.json()["chars_total"]


def test_extract_refuses_unsupported_files(client, user):
    r = client.post("/api/books/extract", files={"file": ("x.rtf", b"hi")}, cookies=user["cookies"])
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]


def test_extract_requires_login(client):
    assert client.post("/api/books/extract", files={"file": ("x.txt", b"hello there")}).status_code == 401
