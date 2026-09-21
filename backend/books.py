import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import pricing
from credits import ensure_monthly_stipend, get_balance, release_reservation, reserve_credits
from db import get_pool
from deps import get_current_user, to_uuid
from generation import LENGTH_CHAPTERS, run_generation
from pdf_export import build_book_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books")


class CharacterSeedIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field("", max_length=100)
    description: str = Field("", max_length=500)


class CreateBookIn(BaseModel):
    book_type: str = Field(pattern="^(novel|memoir|biography)$")
    prompt: str = Field(min_length=10, max_length=4000)
    genre: str = ""
    tone: str = ""
    setting: str = Field("", max_length=2000)
    backstory: str = Field("", max_length=3000)
    chapter_outline: str = Field("", max_length=6000)
    characters: list[CharacterSeedIn] = Field(default_factory=list, max_length=12)
    length: str = Field(pattern="^(short|medium|long)$")
    style: str = "house"
    style_secondary_a: Optional[str] = None
    style_secondary_b: Optional[str] = None


class UpdateChapterIn(BaseModel):
    content: str


class TableIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    columns: list[str] = Field(default_factory=list, max_length=20)


class TableUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    columns: Optional[list[str]] = Field(None, max_length=20)
    rows: Optional[list[dict]] = Field(None, max_length=500)


def serialize_table(t: dict) -> dict:
    return {
        "id": str(t["id"]),
        "book_id": str(t["book_id"]),
        "name": t["name"],
        "columns": t.get("columns", []),
        "rows": t.get("rows", []),
        "created_at": _iso(t.get("created_at")),
        "updated_at": _iso(t.get("updated_at")),
    }


class UpdateBibleIn(BaseModel):
    premise: Optional[str] = Field(None, max_length=4000)
    characters: Optional[list[CharacterSeedIn]] = Field(None, max_length=30)
    plot_threads: Optional[list[str]] = Field(None, max_length=30)


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def serialize_book(b: dict) -> dict:
    reveal = bool(b.get("illustrations_unlocked"))
    return {
        "id": str(b["id"]),
        "user_id": str(b["user_id"]),
        "title": b.get("title", "Untitled"),
        "book_type": b["book_type"],
        "genre": b.get("genre", ""),
        "tone": b.get("tone", ""),
        "length": b["length"],
        "style": b.get("style", "house"),
        "prompt": b["prompt"],
        "premise": b.get("premise", ""),
        "characters": b.get("characters", []),
        "plot_threads": b.get("plot_threads", []),
        "outline": b.get("outline", []),
        "total_chapters": b.get("total_chapters", 0),
        "current_chapter": b.get("current_chapter", 0),
        "status": b.get("status", "pending"),
        "error": b.get("error"),
        "cover_image_url": b.get("cover_image_url") if reveal else None,
        "has_cover_image": bool(b.get("cover_image_url")),
        "illustrations_unlocked": reveal,
        "pdf_unlocked": bool(b.get("pdf_unlocked")),
        "created_at": _iso(b.get("created_at")),
        "updated_at": _iso(b.get("updated_at")),
    }


def serialize_chapter(c: dict, reveal_images: bool) -> dict:
    return {
        "id": str(c["id"]),
        "book_id": str(c["book_id"]),
        "index": c["index"],
        "title": c["title"],
        "content": c.get("content", ""),
        "word_count": c.get("word_count", 0),
        "status": c.get("status", "pending"),
        "image_url": c.get("image_url") if reveal_images else None,
        "has_image": bool(c.get("image_url")),
    }


async def _get_owned_book(book_id: str, user: dict) -> dict:
    """Fetch a book by id, scoped to its owner. Every book route needs exactly
    this: a 404 for a malformed id, a missing book, and someone else's book
    alike — the three are indistinguishable to a caller who owns none of them."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "select * from books where id = $1 and user_id = $2",
        to_uuid(book_id, "Book not found"), str(user["id"]),
    )
    if not row:
        raise HTTPException(404, "Book not found")
    return dict(row)


def _validate_style(user_tier: str, style: str, style_secondary_a: Optional[str], style_secondary_b: Optional[str]):
    allowed = set(pricing.allowed_styles_for_tier(user_tier))
    if style not in allowed:
        raise HTTPException(403, f"Style '{style}' requires a higher tier. Upgrade or pick an unlocked style.")
    if style == pricing.CHIMERA_KEY:
        if not style_secondary_a or not style_secondary_b or style_secondary_a == style_secondary_b:
            raise HTTPException(400, "Chimera Blend requires two distinct base writer styles.")
        for s in (style_secondary_a, style_secondary_b):
            if s not in pricing.WRITER_STYLES:
                raise HTTPException(400, f"Unknown base style for Chimera Blend: {s}")


@router.post("")
async def create_book(body: CreateBookIn, user=Depends(get_current_user)):
    await ensure_monthly_stipend(user)
    tier = user.get("tier", "apprentice")
    _validate_style(tier, body.style, body.style_secondary_a, body.style_secondary_b)

    total_chapters = LENGTH_CHAPTERS.get(body.length, 8)
    multiplier = pricing.style_multiplier(body.style, body.style_secondary_a, body.style_secondary_b)
    estimated_cost = pricing.estimate_word_cost(total_chapters, multiplier)
    balance = await get_balance(str(user["id"]))
    if balance < estimated_cost:
        raise HTTPException(402, f"Not enough Neural Credits. This book needs ~{estimated_cost} NC, you have {balance} NC. Visit the Store to top up.")

    composed_prompt = body.prompt
    if body.setting.strip():
        composed_prompt += f"\n\nSetting: {body.setting.strip()}"
    if body.backstory.strip():
        composed_prompt += f"\n\nBackstory: {body.backstory.strip()}"
    if body.chapter_outline.strip():
        composed_prompt += (
            "\n\nAuthor-provided chapter outline — use this exact chapter breakdown "
            "(expand each entry into a full chapter; do not invent a different structure "
            "or a different chapter count than what's listed here):\n"
            f"{body.chapter_outline.strip()}"
        )
    seed_characters = [c.model_dump() for c in body.characters]

    pool = await get_pool()
    now = datetime.now(timezone.utc)
    row = await pool.fetchrow(
        """insert into books (
             user_id, title, book_type, genre, tone, length, style,
             style_secondary_a, style_secondary_b, prompt, characters, total_chapters,
             reserved_nc, settled, created_at, updated_at
           ) values ($1,'Generating...',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,false,$13,$13)
           returning *""",
        str(user["id"]), body.book_type, body.genre, body.tone, body.length, body.style,
        body.style_secondary_a, body.style_secondary_b, composed_prompt, seed_characters, total_chapters,
        estimated_cost, now,
    )
    book_doc = dict(row)
    book_id = str(book_doc["id"])

    # Take the estimate up front. The balance read above only produces a good
    # error message; this is the check that actually holds, because it debits
    # and verifies affordability in one atomic update. Without it, books
    # requested concurrently each pass their own read-then-write check and the
    # balance goes as negative as the user has parallel requests.
    reserved = await reserve_credits(
        str(user["id"]), estimated_cost,
        f"Reserved for book generation (~{estimated_cost} NC)",
        related_book_id=book_id,
    )
    if reserved is None:
        await pool.execute("delete from books where id = $1", book_doc["id"])
        current = await get_balance(str(user["id"]))
        raise HTTPException(402, f"Not enough Neural Credits. This book needs ~{estimated_cost} NC, you have {current} NC. Visit the Store to top up.")

    asyncio.create_task(run_generation(book_id))
    return serialize_book(book_doc)


@router.get("")
async def list_books(user=Depends(get_current_user)):
    pool = await get_pool()
    rows = await pool.fetch(
        "select * from books where user_id = $1 order by created_at desc limit 200",
        str(user["id"]),
    )
    return [serialize_book(dict(b)) for b in rows]


@router.get("/{book_id}")
async def get_book(book_id: str, user=Depends(get_current_user)):
    return serialize_book(await _get_owned_book(book_id, user))


@router.get("/{book_id}/chapters")
async def list_chapters(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    reveal = bool(book.get("illustrations_unlocked"))
    pool = await get_pool()
    rows = await pool.fetch("select * from chapters where book_id = $1 order by index asc limit 200", book["id"])
    return [serialize_chapter(dict(c), reveal) for c in rows]


@router.patch("/{book_id}/chapters/{chapter_id}")
async def update_chapter(book_id: str, chapter_id: str, body: UpdateChapterIn, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    word_count = len(body.content.split())
    pool = await get_pool()
    # One scoped round-trip that both writes and returns the chapter. Scoping
    # only by chapter_id would hand back any chapter whose id a caller can
    # name, including chapters of books they do not own.
    row = await pool.fetchrow(
        """update chapters set content = $3, word_count = $4, updated_at = $5
           where id = $1 and book_id = $2
           returning *""",
        to_uuid(chapter_id, "Chapter not found"), book["id"], body.content, word_count, datetime.now(timezone.utc),
    )
    if not row:
        raise HTTPException(404, "Chapter not found")
    return serialize_chapter(dict(row), reveal_images=bool(book.get("illustrations_unlocked")))


@router.post("/{book_id}/unlock-illustrations")
async def unlock_illustrations(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    if book.get("illustrations_unlocked"):
        return serialize_book(book)
    cost = pricing.ILLUSTRATION_UNLOCK_COST
    charged = await reserve_credits(
        str(user["id"]), cost,
        f"Unlocked illustrations for '{book.get('title', 'book')}'",
        tx_type="purchase", related_book_id=book_id,
    )
    if charged is None:
        balance = await get_balance(str(user["id"]))
        raise HTTPException(402, f"Not enough Neural Credits. Unlocking illustrations costs {cost} NC, you have {balance} NC.")
    pool = await get_pool()
    updated = await pool.fetchrow(
        """update books set illustrations_unlocked = true, updated_at = $2
           where id = $1 and illustrations_unlocked = false
           returning *""",
        book["id"], datetime.now(timezone.utc),
    )
    if not updated:
        # Two unlock requests raced; only one of them should have paid.
        await release_reservation(str(user["id"]), cost, f"Refund: illustrations already unlocked for '{book.get('title', 'book')}'", related_book_id=book_id)
        return serialize_book(book | {"illustrations_unlocked": True})
    return serialize_book(dict(updated))


@router.delete("/{book_id}")
async def delete_book(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    pool = await get_pool()
    # Chapters cascade on the FK; deleting the book is enough.
    await pool.execute("delete from books where id = $1 and user_id = $2", book["id"], str(user["id"]))
    return {"ok": True}


@router.get("/{book_id}/pdf")
async def export_pdf(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    if book.get("status") != "completed":
        raise HTTPException(400, "Book is not fully generated yet.")

    cost = pricing.PDF_EXPORT_COST
    charged = False
    if not book.get("pdf_unlocked"):
        paid = await reserve_credits(
            str(user["id"]), cost,
            f"PDF export unlocked for '{book.get('title', 'book')}'",
            tx_type="purchase", related_book_id=book_id,
        )
        if paid is None:
            balance = await get_balance(str(user["id"]))
            raise HTTPException(402, f"Not enough Neural Credits. PDF export costs {cost} NC, you have {balance} NC.")
        charged = True

    pool = await get_pool()
    rows = await pool.fetch("select * from chapters where book_id = $1 order by index asc limit 200", book["id"])
    chapters = [dict(r) for r in rows]
    try:
        # build_book_pdf is synchronous and slow by nature: reportlab layout is
        # CPU-bound and it fetches one illustration per chapter over the
        # network. Off the event loop or it stalls every other request for
        # the length of the export.
        pdf_bytes = await asyncio.to_thread(build_book_pdf, book, chapters)
    except Exception:
        # Only mark the export unlocked once one has actually been produced —
        # otherwise a failed render bills the user for a file they never got.
        if charged:
            await release_reservation(str(user["id"]), cost, f"Refund: PDF export failed for '{book.get('title', 'book')}'", related_book_id=book_id)
        logger.exception("PDF export failed for book %s", book_id)
        raise HTTPException(500, "Could not build the PDF. You have not been charged — please try again.")

    if charged:
        await pool.execute("update books set pdf_unlocked = true, updated_at = $2 where id = $1", book["id"], datetime.now(timezone.utc))

    safe_title = "".join(c for c in book.get("title", "book") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "book"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_title}.pdf"},
    )


MAX_TABLES_PER_BOOK = 20


@router.get("/{book_id}/tables")
async def list_tables(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    pool = await get_pool()
    rows = await pool.fetch("select * from book_tables where book_id = $1 order by created_at asc", book["id"])
    return [serialize_table(dict(r)) for r in rows]


@router.post("/{book_id}/tables")
async def create_table(book_id: str, body: TableIn, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    pool = await get_pool()
    existing_count = await pool.fetchval("select count(*) from book_tables where book_id = $1", book["id"])
    if existing_count >= MAX_TABLES_PER_BOOK:
        raise HTTPException(400, f"This book already has the maximum of {MAX_TABLES_PER_BOOK} tables.")
    now = datetime.now(timezone.utc)
    row = await pool.fetchrow(
        """insert into book_tables (book_id, name, columns, rows, created_at, updated_at)
           values ($1, $2, $3, '[]'::jsonb, $4, $4) returning *""",
        book["id"], body.name, body.columns, now,
    )
    return serialize_table(dict(row))


@router.patch("/{book_id}/tables/{table_id}")
async def update_table(book_id: str, table_id: str, body: TableUpdateIn, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    pool = await get_pool()
    existing = await pool.fetchrow(
        "select * from book_tables where id = $1 and book_id = $2",
        to_uuid(table_id, "Table not found"), book["id"],
    )
    if not existing:
        raise HTTPException(404, "Table not found")
    name = body.name if body.name is not None else existing["name"]
    columns = body.columns if body.columns is not None else existing["columns"]
    rows_val = body.rows if body.rows is not None else existing["rows"]
    row = await pool.fetchrow(
        "update book_tables set name=$2, columns=$3, rows=$4, updated_at=$5 where id=$1 returning *",
        existing["id"], name, columns, rows_val, datetime.now(timezone.utc),
    )
    return serialize_table(dict(row))


@router.delete("/{book_id}/tables/{table_id}")
async def delete_table(book_id: str, table_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    pool = await get_pool()
    await pool.execute(
        "delete from book_tables where id = $1 and book_id = $2",
        to_uuid(table_id, "Table not found"), book["id"],
    )
    return {"ok": True}
