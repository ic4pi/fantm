import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from db import db
from deps import get_current_user
from generation import run_generation, LENGTH_CHAPTERS
from pdf_export import build_book_pdf
import pricing
from credits import ensure_monthly_stipend, adjust_balance, get_balance

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
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    res = await db.books.insert_one(book_doc)
    book_id = str(res.inserted_id)
    asyncio.create_task(run_generation(book_id, db))
    book_doc["_id"] = res.inserted_id
    return serialize_book(book_doc)


@router.get("")
async def list_books(user=Depends(get_current_user)):
    books = await db.books.find({"user_id": str(user["_id"])}).sort("created_at", -1).to_list(200)
    return [serialize_book(b) for b in books]


@router.get("/{book_id}")
async def get_book(book_id: str, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    return serialize_book(book)


@router.get("/{book_id}/chapters")
async def list_chapters(book_id: str, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    reveal = bool(book.get("illustrations_unlocked"))
    chapters = await db.chapters.find({"book_id": book_id}).sort("index", 1).to_list(200)
    return [serialize_chapter(c, reveal) for c in chapters]


@router.patch("/{book_id}/chapters/{chapter_id}")
async def update_chapter(book_id: str, chapter_id: str, body: UpdateChapterIn, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    word_count = len(body.content.split())
    await db.chapters.update_one(
        {"_id": ObjectId(chapter_id), "book_id": book_id},
        {"$set": {"content": body.content, "word_count": word_count, "updated_at": datetime.now(timezone.utc)}},
    )
    chapter = await db.chapters.find_one({"_id": ObjectId(chapter_id)})
    return serialize_chapter(chapter, reveal_images=bool(book.get("illustrations_unlocked")))


@router.post("/{book_id}/unlock-illustrations")
async def unlock_illustrations(book_id: str, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    if book.get("illustrations_unlocked"):
        return serialize_book(book)
    cost = pricing.ILLUSTRATION_UNLOCK_COST
    balance = await get_balance(str(user["_id"]))
    if balance < cost:
        raise HTTPException(402, f"Not enough Neural Credits. Unlocking illustrations costs {cost} NC, you have {balance} NC.")
    await adjust_balance(str(user["_id"]), -cost, "purchase", f"Unlocked illustrations for '{book.get('title', 'book')}'", related_book_id=book_id)
    await db.books.update_one({"_id": ObjectId(book_id)}, {"$set": {"illustrations_unlocked": True, "updated_at": datetime.now(timezone.utc)}})
    book["illustrations_unlocked"] = True
    return serialize_book(book)


@router.delete("/{book_id}")
async def delete_book(book_id: str, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    await db.books.delete_one({"_id": ObjectId(book_id)})
    await db.chapters.delete_many({"book_id": book_id})
    return {"ok": True}


@router.get("/{book_id}/pdf")
async def export_pdf(book_id: str, user=Depends(get_current_user)):
    book = await db.books.find_one({"_id": ObjectId(book_id), "user_id": str(user["_id"])})
    if not book:
        raise HTTPException(404, "Book not found")
    if book.get("status") != "completed":
        raise HTTPException(400, "Book is not fully generated yet.")
    if not book.get("pdf_unlocked"):
        cost = pricing.PDF_EXPORT_COST
        balance = await get_balance(str(user["_id"]))
        if balance < cost:
            raise HTTPException(402, f"Not enough Neural Credits. PDF export costs {cost} NC, you have {balance} NC.")
        await adjust_balance(str(user["_id"]), -cost, "purchase", f"PDF export unlocked for '{book.get('title', 'book')}'", related_book_id=book_id)
        await db.books.update_one({"_id": ObjectId(book_id)}, {"$set": {"pdf_unlocked": True, "updated_at": datetime.now(timezone.utc)}})
    chapters = await db.chapters.find({"book_id": book_id}).sort("index", 1).to_list(200)
    pdf_bytes = build_book_pdf(book, chapters)
    safe_title = "".join(c for c in book.get("title", "book") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "book"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_title}.pdf"},
    )
