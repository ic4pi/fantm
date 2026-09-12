import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from db import db
from deps import get_current_user, to_object_id
from generation import run_generation, LENGTH_CHAPTERS
from pdf_export import build_book_pdf
import pricing
from credits import ensure_monthly_stipend, get_balance, reserve_credits, release_reservation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books")


class CreateBookIn(BaseModel):
    book_type: str = Field(pattern="^(novel|memoir|biography)$")
    prompt: str = Field(min_length=10, max_length=2000)
    genre: str = ""
    tone: str = ""
    length: str = Field(pattern="^(short|medium|long)$")
    style: str = "house"
    style_secondary_a: Optional[str] = None
    style_secondary_b: Optional[str] = None


class UpdateChapterIn(BaseModel):
    content: str


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def serialize_book(b: dict) -> dict:
    reveal = bool(b.get("illustrations_unlocked"))
    return {
        "id": str(b["_id"]),
        "user_id": b["user_id"],
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
        "id": str(c["_id"]),
        "book_id": c["book_id"],
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
    book = await db.books.find_one({
        "_id": to_object_id(book_id, "Book not found"),
        "user_id": str(user["_id"]),
    })
    if not book:
        raise HTTPException(404, "Book not found")
    return book


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
    balance = await get_balance(str(user["_id"]))
    if balance < estimated_cost:
        raise HTTPException(402, f"Not enough Neural Credits. This book needs ~{estimated_cost} NC, you have {balance} NC. Visit the Store to top up.")

    book_doc = {
        "user_id": str(user["_id"]),
        "title": "Generating...",
        "book_type": body.book_type,
        "genre": body.genre,
        "tone": body.tone,
        "length": body.length,
        "style": body.style,
        "style_secondary_a": body.style_secondary_a,
        "style_secondary_b": body.style_secondary_b,
        "prompt": body.prompt,
        "premise": "",
        "characters": [],
        "plot_threads": [],
        "running_summary": "",
        "outline": [],
        "total_chapters": total_chapters,
        "current_chapter": 0,
        "status": "pending",
        "error": None,
        "cover_image_url": None,
        "illustrations_unlocked": False,
        "pdf_unlocked": False,
        "reserved_nc": estimated_cost,
        "settled": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res = await db.books.insert_one(book_doc)
    book_id = str(res.inserted_id)

    # Take the estimate up front. The balance read above only produces a good
    # error message; this is the check that actually holds, because it debits
    # and verifies affordability in one atomic update. Without it, books
    # requested concurrently each pass their own read-then-write check and the
    # balance goes as negative as the user has parallel requests.
    reserved = await reserve_credits(
        str(user["_id"]), estimated_cost,
        f"Reserved for book generation (~{estimated_cost} NC)",
        related_book_id=book_id,
    )
    if reserved is None:
        await db.books.delete_one({"_id": res.inserted_id})
        current = await get_balance(str(user["_id"]))
        raise HTTPException(402, f"Not enough Neural Credits. This book needs ~{estimated_cost} NC, you have {current} NC. Visit the Store to top up.")

    asyncio.create_task(run_generation(book_id, db))
    book_doc["_id"] = res.inserted_id
    return serialize_book(book_doc)


@router.get("")
async def list_books(user=Depends(get_current_user)):
    books = await db.books.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(200)
    return [serialize_book(b) for b in books]


@router.get("/{book_id}")
async def get_book(book_id: str, user=Depends(get_current_user)):
    return serialize_book(await _get_owned_book(book_id, user))


@router.get("/{book_id}/chapters")
async def list_chapters(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    reveal = bool(book.get("illustrations_unlocked"))
    chapters = await db.chapters.find({"book_id": book_id}).sort("index", 1).to_list(200)
    return [serialize_chapter(c, reveal) for c in chapters]


@router.patch("/{book_id}/chapters/{chapter_id}")
async def update_chapter(book_id: str, chapter_id: str, body: UpdateChapterIn, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    word_count = len(body.content.split())
    # One scoped round-trip that both writes and returns the chapter. Reading
    # it back separately would need the same book_id filter repeated, and a
    # read scoped only by chapter_id hands back any chapter whose id a caller
    # can name, including chapters of books they do not own.
    chapter = await db.chapters.find_one_and_update(
        {"_id": to_object_id(chapter_id, "Chapter not found"), "book_id": book_id},
        {"$set": {"content": body.content, "word_count": word_count, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    return serialize_chapter(chapter, reveal_images=bool(book.get("illustrations_unlocked")))


@router.post("/{book_id}/unlock-illustrations")
async def unlock_illustrations(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    if book.get("illustrations_unlocked"):
        return serialize_book(book)
    cost = pricing.ILLUSTRATION_UNLOCK_COST
    charged = await reserve_credits(
        str(user["_id"]), cost,
        f"Unlocked illustrations for '{book.get('title', 'book')}'",
        tx_type="purchase", related_book_id=book_id,
    )
    if charged is None:
        balance = await get_balance(str(user["_id"]))
        raise HTTPException(402, f"Not enough Neural Credits. Unlocking illustrations costs {cost} NC, you have {balance} NC.")
    result = await db.books.update_one(
        {"_id": book["_id"], "illustrations_unlocked": {"$ne": True}},
        {"$set": {"illustrations_unlocked": True, "updated_at": datetime.now(timezone.utc)}},
    )
    if not result.modified_count:
        # Two unlock requests raced; only one of them should have paid.
        await release_reservation(str(user["_id"]), cost, f"Refund: illustrations already unlocked for '{book.get('title', 'book')}'", related_book_id=book_id)
    book["illustrations_unlocked"] = True
    return serialize_book(book)


@router.delete("/{book_id}")
async def delete_book(book_id: str, user=Depends(get_current_user)):
    book = await _get_owned_book(book_id, user)
    await db.books.delete_one({"_id": book["_id"]})
    await db.chapters.delete_many({"book_id": book_id})
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
            str(user["_id"]), cost,
            f"PDF export unlocked for '{book.get('title', 'book')}'",
            tx_type="purchase", related_book_id=book_id,
        )
        if paid is None:
            balance = await get_balance(str(user["_id"]))
            raise HTTPException(402, f"Not enough Neural Credits. PDF export costs {cost} NC, you have {balance} NC.")
        charged = True

    chapters = await db.chapters.find({"book_id": book_id}).sort("index", 1).to_list(200)
    try:
        # build_book_pdf is synchronous and slow by nature: reportlab layout is
        # CPU-bound and it fetches one illustration per chapter over the
        # network. Run on the event loop it stalls every other request for the
        # length of the export.
        pdf_bytes = await asyncio.to_thread(build_book_pdf, book, chapters)
    except Exception:
        # Only mark the export unlocked once one has actually been produced —
        # otherwise a failed render bills the user for a file they never got.
        if charged:
            await release_reservation(str(user["_id"]), cost, f"Refund: PDF export failed for '{book.get('title', 'book')}'", related_book_id=book_id)
        logger.exception("PDF export failed for book %s", book_id)
        raise HTTPException(500, "Could not build the PDF. You have not been charged — please try again.")

    if charged:
        await db.books.update_one({"_id": book["_id"]}, {"$set": {"pdf_unlocked": True, "updated_at": datetime.now(timezone.utc)}})

    safe_title = "".join(c for c in book.get("title", "book") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "book"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_title}.pdf"},
    )
