import os
import json
import re
import asyncio
import logging
import hashlib
from urllib.parse import quote
from datetime import datetime, timezone
from bson import ObjectId
from groq import Groq
from json_repair import repair_json
import pricing
import chat_providers
from credits import adjust_balance

logger = logging.getLogger(__name__)

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

LENGTH_CHAPTERS = {"short": 5, "medium": 8, "long": 12}
TYPE_LABELS = {"novel": "novel", "memoir": "memoir", "biography": "biography"}


def _chat(messages, max_tokens=2000, temperature=0.85):
    """House-model chat — always Groq, regardless of the book's chosen
    style. Used for outline generation and continuity-state tracking,
    which are internal bookkeeping calls, not the voice being paid for."""
    for attempt in range(3):
        try:
            completion = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=temperature, max_completion_tokens=max_tokens
            )
            return completion.choices[0].message.content
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning("Groq call failed (attempt %s): %s", attempt + 1, e)
    return ""


def _resolve_style_provider(book: dict) -> tuple[str, str]:
    """Which (provider, model) actually writes this book's chapters. For
    Chimera Blend, the primary style's model does the writing — its prompt
    text is instructed to fuse in the secondary voice — since one call
    needs one concrete model regardless of how many voices it's blending."""
    style = book.get("style", "house")
    if style == pricing.CHIMERA_KEY:
        primary_key = book.get("style_secondary_a", "gothic_romantic")
        primary = pricing.WRITER_STYLES.get(primary_key, pricing.WRITER_STYLES["house"])
        return primary["provider"], primary["model"]
    entry = pricing.WRITER_STYLES.get(style, pricing.WRITER_STYLES["house"])
    return entry["provider"], entry["model"]


def _chat_for_chapter(book: dict, messages, max_tokens=2200, temperature=0.85) -> str:
    """Routes the actual chapter-prose call to whichever provider/model the
    book's style is assigned to — this is what makes the NC multiplier real
    instead of decorative. Falls back to the free House model if the styled
    provider errors out, so a flaky third-party model doesn't hard-fail a
    whole book generation run."""
    provider, model = _resolve_style_provider(book)
    if provider == "groq":
        return _chat(messages, max_tokens=max_tokens, temperature=temperature)
    try:
        return chat_providers.chat_complete(provider, model, messages, max_tokens=max_tokens, temperature=temperature)
    except Exception as e:
        logger.warning("Styled provider '%s/%s' failed (%s) — falling back to House for this chapter.", provider, model, e)
        return _chat(messages, max_tokens=max_tokens, temperature=temperature)



def _parse_json_loose(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(repair_json(text))


def generate_outline(book: dict) -> dict:
    n_chapters = LENGTH_CHAPTERS.get(book["length"], 8)
    label = TYPE_LABELS.get(book["book_type"], "book")
    system = (
        f"You are a master {label} writer and story architect. "
        "Design a coherent long-form book outline. Respond ONLY with valid raw JSON, no markdown fences, no commentary."
    )
    user = f"""Create a book outline for a {book['book_type']} with genre "{book['genre']}" and tone "{book['tone']}".
User's prompt/premise: {book['prompt']}

Return JSON with this exact shape:
{{
  "title": "book title",
  "premise": "2-3 sentence expanded premise",
  "characters": [{{"name": "...", "role": "...", "description": "..."}}],
  "plot_threads": ["thread 1", "thread 2"],
  "chapters": [{{"title": "...", "summary": "1-2 sentence summary of what happens"}}]
}}

Generate exactly {n_chapters} chapters that form a complete, coherent {label} arc with a beginning, middle and satisfying ending."""
    raw = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=3000, temperature=0.9)
    return _parse_json_loose(raw)


def _style_prompt(book: dict) -> str:
    style = book.get("style", "house")
    if style == pricing.CHIMERA_KEY:
        primary = pricing.WRITER_STYLES.get(book.get("style_secondary_a", "gothic_romantic"), {}).get("prompt", "")
        secondary = pricing.WRITER_STYLES.get(book.get("style_secondary_b", "noir_detective"), {}).get("prompt", "")
        return f"Blend two voices (Chimera Blend): (1) {primary} (2) {secondary} Fuse both into one distinctive hybrid voice."
    return pricing.WRITER_STYLES.get(style, pricing.WRITER_STYLES["house"]).get("prompt", "")


def generate_chapter_content(book: dict, chapter_brief: dict, chapter_index: int, total: int, remaining_briefs: list = None) -> str:
    characters_desc = "\n".join(f"- {c.get('name')} ({c.get('role', '')}): {c.get('description', '')}" for c in book.get("characters", []))
    threads_desc = "\n".join(f"- {t}" for t in book.get("plot_threads", []))
    label = TYPE_LABELS.get(book["book_type"], "book")
    style_instruction = _style_prompt(book)
    system = (
        f"You are a master {label} writer, writing chapter {chapter_index + 1} of {total}. "
        f"Tone: {book['tone']}. Genre: {book['genre']}. "
        + (f"{style_instruction} " if style_instruction else "")
        + "Write vivid, coherent, well-paced prose that continues the story forward without repeating earlier events. "
        "Do not include the chapter title or number in the body, output only the prose content."
    )
    upcoming = remaining_briefs or []
    upcoming_desc = "\n".join(
        f"- Ch {chapter_index + 2 + i}: \"{b.get('title')}\" — {b.get('summary')}" for i, b in enumerate(upcoming)
    )
    user = f"""Book premise: {book.get('premise', '')}

Characters:
{characters_desc or 'N/A'}

Ongoing plot threads:
{threads_desc or 'N/A'}

Story so far (running summary): {book.get('running_summary') or 'This is the first chapter.'}

Planned remaining chapters (for your awareness — write only THIS chapter, but keep these headed toward correctly):
{upcoming_desc or 'This is the final chapter — bring the story to a satisfying close.'}

This chapter's brief — "{chapter_brief.get('title')}": {chapter_brief.get('summary')}

Write the full chapter now (aim for 700-1200 words)."""
    return _chat_for_chapter(book, [{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=2200, temperature=0.85)


def _summary_word_budget(total_chapters: int) -> int:
    # Fixed 200-word cap loses early-chapter nuance by book's end on longer
    # books — scale the budget with how much story there'll be to compress.
    return max(200, 90 + 15 * total_chapters)


def update_story_state(book: dict, chapter_content: str, total_chapters: int = None) -> dict:
    budget = _summary_word_budget(total_chapters or len(book.get("outline", [])) or 5)
    system = "You track story continuity for a long-form book generator. Respond ONLY with valid raw JSON, no markdown fences, no commentary."
    user = f"""Current running summary: {book.get('running_summary') or 'None yet.'}
Current characters: {json.dumps(book.get('characters', []))}
Current plot threads: {json.dumps(book.get('plot_threads', []))}

New chapter content just written:
{chapter_content[:4000]}

Update and return JSON with this exact shape:
{{
  "running_summary": "updated running summary of the whole story so far, max {budget} words — preserve early plot details and setups that later chapters still need, not just recent events",
  "characters": [{{"name": "...", "role": "...", "description": "..."}}],
  "plot_threads": ["updated list of open plot threads"]
}}"""
    raw = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=max(1200, budget * 3), temperature=0.4)
    return _parse_json_loose(raw)




STYLE_SUFFIX = "moody gothic illustration, retro futuristic, cinematic dark atmosphere, detailed, no text, no watermark"


def _base_seed(book_id: str) -> int:
    return int(hashlib.sha256(book_id.encode()).hexdigest(), 16) % (10 ** 8)


def build_illustration_url(prompt: str, seed: int, width: int = 1024, height: int = 1024) -> str:
    full_prompt = f"{prompt}, {STYLE_SUFFIX}"
    encoded = quote(full_prompt, safe="")
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&model=flux"


def build_cover_url(book_id: str, title: str, premise: str) -> str:
    return build_illustration_url(f"book cover art for '{title}': {premise[:200]}", _base_seed(book_id), width=1024, height=1536)


def build_chapter_illustration_url(book_id: str, idx: int, chapter_title: str, summary: str) -> str:
    return build_illustration_url(f"{chapter_title}: {summary[:200]}", _base_seed(book_id) + idx + 1, width=1024, height=576)


async def run_generation(book_id: str, db):
    oid = ObjectId(book_id)
    book_doc = await db.books.find_one({"_id": oid})
    if not book_doc:
        return
    user_id = book_doc["user_id"]
    multiplier = pricing.style_multiplier(
        book_doc.get("style", "house"),
        style_secondary_a=book_doc.get("style_secondary_a"),
        style_secondary_b=book_doc.get("style_secondary_b"),
    )
    try:
        outline = await asyncio.to_thread(generate_outline, book_doc)
        chapters_brief = outline.get("chapters", [])
        title = outline.get("title", book_doc["title"])
        premise = outline.get("premise", "")
        cover_image_url = build_cover_url(book_id, title, premise)
        await db.books.update_one({"_id": oid}, {"$set": {
            "title": title,
            "premise": premise,
            "characters": outline.get("characters", []),
            "plot_threads": outline.get("plot_threads", []),
            "outline": chapters_brief,
            "total_chapters": len(chapters_brief),
            "cover_image_url": cover_image_url,
            "status": "generating",
            "updated_at": datetime.now(timezone.utc),
        }})
        book_doc = await db.books.find_one({"_id": oid})

        for idx, brief in enumerate(chapters_brief):
            chapter_doc = {
                "book_id": book_id,
                "index": idx,
                "title": brief.get("title", f"Chapter {idx + 1}"),
                "content": "",
                "word_count": 0,
                "status": "generating",
                "image_url": build_chapter_illustration_url(book_id, idx, brief.get("title", ""), brief.get("summary", "")),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            res = await db.chapters.insert_one(chapter_doc)
            await db.books.update_one({"_id": oid}, {"$set": {"current_chapter": idx + 1, "updated_at": datetime.now(timezone.utc)}})

            content = await asyncio.to_thread(
                generate_chapter_content, book_doc, brief, idx, len(chapters_brief), chapters_brief[idx + 1:]
            )
            word_count = len(content.split())
            burn = round(word_count * multiplier)
            await db.chapters.update_one({"_id": res.inserted_id}, {"$set": {
                "content": content, "word_count": word_count, "status": "done", "updated_at": datetime.now(timezone.utc),
            }})
            await adjust_balance(user_id, -burn, "burn", f"Chapter {idx + 1} generation ({word_count} words)", related_book_id=book_id)

            state = await asyncio.to_thread(update_story_state, book_doc, content, len(chapters_brief))
            book_doc["running_summary"] = state.get("running_summary", book_doc.get("running_summary", ""))
            book_doc["characters"] = state.get("characters", book_doc.get("characters", []))
            book_doc["plot_threads"] = state.get("plot_threads", book_doc.get("plot_threads", []))
            await db.books.update_one({"_id": oid}, {"$set": {
                "running_summary": book_doc["running_summary"],
                "characters": book_doc["characters"],
                "plot_threads": book_doc["plot_threads"],
                "updated_at": datetime.now(timezone.utc),
            }})

        await db.books.update_one({"_id": oid}, {"$set": {"status": "completed", "updated_at": datetime.now(timezone.utc)}})
    except Exception as e:
        logger.exception("Generation failed for book %s", book_id)
        await db.books.update_one({"_id": oid}, {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.now(timezone.utc)}})
