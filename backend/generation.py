import os
import json
import re
import asyncio
import logging
import hashlib
from urllib.parse import quote
from datetime import datetime, timezone
from groq import Groq
from json_repair import repair_json
import pricing
import chat_providers
from credits import settle_reservation
from db import get_pool

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
        primary_key = book.get("style_secondary_a", "anne_rousseau")
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
    seed_characters = book.get("characters") or []
    characters_block = ""
    if seed_characters:
        listed = "\n".join(
            f"- {c.get('name')} ({c.get('role', '')}): {c.get('description', '')}" for c in seed_characters
        )
        characters_block = (
            "\nThe author has already defined these characters — use them exactly as given "
            "(do not rename, contradict, or replace them; you may add supporting characters as needed). "
            f'Your JSON response\'s "characters" list must include all of them verbatim:\n{listed}\n'
        )
    world_rules = book.get("world_rules") or []
    world_rules_block = ""
    if world_rules:
        listed_rules = "\n".join(f"- {r}" for r in world_rules)
        world_rules_block = (
            "\nSpecial rules for how this world works, or story elements to draw on — "
            "these override normal-world logic where they apply. Not every one has to appear; "
            f"use what fits:\n{listed_rules}\n"
        )
    user = f"""Create a book outline for a {book['book_type']} with genre "{book['genre']}" and tone "{book['tone']}".
User's prompt/premise: {book['prompt']}
{characters_block}{world_rules_block}
Return JSON with this exact shape:
{{
  "title": "book title",
  "premise": "2-3 sentence expanded premise",
  "characters": [{{"name": "...", "role": "...", "description": "..."}}],
  "plot_threads": ["thread 1", "thread 2"],
  "chapters": [{{"title": "...", "summary": "1-2 sentence summary of what happens"}}]
}}

{
    "Follow the author-provided chapter outline above for how many chapters there are and "
    "what happens in each one — do not default to a different chapter count."
    if "Author-provided chapter outline" in book.get("prompt", "")
    else f"Generate exactly {n_chapters} chapters that form a complete, coherent {label} arc with a beginning, middle and satisfying ending."
}"""
    raw = _chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=3000, temperature=0.9)
    return _parse_json_loose(raw)


def _style_prompt(book: dict) -> str:
    style = book.get("style", "house")
    if style == pricing.CHIMERA_KEY:
        primary = pricing.WRITER_STYLES.get(book.get("style_secondary_a", "anne_rousseau"), {}).get("prompt", "")
        secondary = pricing.WRITER_STYLES.get(book.get("style_secondary_b", "raymond_chandley"), {}).get("prompt", "")
        return f"Blend two voices (Chimera Blend): (1) {primary} (2) {secondary} Fuse both into one distinctive hybrid voice."
    return pricing.WRITER_STYLES.get(style, pricing.WRITER_STYLES["house"]).get("prompt", "")


def _render_reference_tables(tables: list) -> str:
    """Freeform author tables (a sports schedule, a timeline, anything) as
    plain text the model can read and stay consistent with — e.g. not
    inventing a score that contradicts one the author already logged."""
    if not tables:
        return ""
    blocks = []
    for t in tables:
        columns = t.get("columns") or []
        rows = t.get("rows") or []
        if not rows:
            continue
        header = " | ".join(columns)
        lines = [" | ".join(str(row.get(col, "")) for col in columns) for row in rows]
        blocks.append(f"[{t.get('name', 'Table')}]\n{header}\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def generate_chapter_content(
    book: dict, chapter_brief: dict, chapter_index: int, total: int,
    remaining_briefs: list = None, reference_tables: list = None,
) -> str:
    characters_desc = "\n".join(f"- {c.get('name')} ({c.get('role', '')}): {c.get('description', '')}" for c in book.get("characters", []))
    threads_desc = "\n".join(f"- {t}" for t in book.get("plot_threads", []))
    world_rules_desc = "\n".join(f"- {r}" for r in book.get("world_rules", []))
    tables_desc = _render_reference_tables(reference_tables or [])
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

Special world rules / satire elements (override normal-world logic where they apply; not all need to appear):
{world_rules_desc or 'N/A'}

Reference tables the author is tracking (stay consistent with any data here):
{tables_desc or 'N/A'}

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


async def run_generation(book_id: str):
    pool = await get_pool()
    book_row = await pool.fetchrow("select * from books where id = $1", book_id)
    if not book_row:
        return
    book_doc = dict(book_row)
    user_id = str(book_doc["user_id"])
    reserved = book_doc.get("reserved_nc", 0)
    actual_burn = 0
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
        await pool.execute(
            """update books set title=$2, premise=$3, characters=$4, plot_threads=$5, outline=$6,
                 total_chapters=$7, cover_image_url=$8, status='generating', updated_at=$9
               where id=$1""",
            book_id, title, premise, outline.get("characters", []), outline.get("plot_threads", []),
            chapters_brief, len(chapters_brief), cover_image_url, datetime.now(timezone.utc),
        )
        book_row = await pool.fetchrow("select * from books where id = $1", book_id)
        book_doc = dict(book_row)

        for idx, brief in enumerate(chapters_brief):
            chapter_row = await pool.fetchrow(
                """insert into chapters (book_id, index, title, content, word_count, status, image_url, created_at, updated_at)
                   values ($1,$2,$3,'',0,'generating',$4,$5,$5) returning id""",
                book_id, idx, brief.get("title", f"Chapter {idx + 1}"),
                build_chapter_illustration_url(book_id, idx, brief.get("title", ""), brief.get("summary", "")),
                datetime.now(timezone.utc),
            )
            chapter_id = chapter_row["id"]
            await pool.execute("update books set current_chapter=$2, updated_at=$3 where id=$1", book_id, idx + 1, datetime.now(timezone.utc))

            # Re-read characters/plot_threads/premise right before writing this
            # chapter — not just carrying the in-memory book_doc forward — so a
            # Story Bible edit made mid-generation actually reaches the next
            # not-yet-written chapter instead of being silently clobbered by
            # the continuity update below (which otherwise writes back
            # whatever book_doc already held before the user's edit).
            fresh = await pool.fetchrow("select characters, plot_threads, premise, world_rules from books where id=$1", book_id)
            if fresh:
                book_doc["characters"] = fresh["characters"]
                book_doc["plot_threads"] = fresh["plot_threads"]
                book_doc["premise"] = fresh["premise"]
                book_doc["world_rules"] = fresh["world_rules"]
            reference_tables = [dict(t) for t in await pool.fetch("select name, columns, rows from book_tables where book_id=$1", book_id)]

            content = await asyncio.to_thread(
                generate_chapter_content, book_doc, brief, idx, len(chapters_brief), chapters_brief[idx + 1:], reference_tables
            )
            word_count = len(content.split())
            burn = round(word_count * multiplier)
            await pool.execute(
                "update chapters set content=$2, word_count=$3, status='done', updated_at=$4 where id=$1",
                chapter_id, content, word_count, datetime.now(timezone.utc),
            )
            actual_burn += burn
            await pool.execute("update books set burned_nc=$2 where id=$1", book_id, actual_burn)

            state = await asyncio.to_thread(update_story_state, book_doc, content, len(chapters_brief))
            book_doc["running_summary"] = state.get("running_summary", book_doc.get("running_summary", ""))
            book_doc["characters"] = state.get("characters", book_doc.get("characters", []))
            book_doc["plot_threads"] = state.get("plot_threads", book_doc.get("plot_threads", []))
            await pool.execute(
                "update books set running_summary=$2, characters=$3, plot_threads=$4, updated_at=$5 where id=$1",
                book_id, book_doc["running_summary"], book_doc["characters"], book_doc["plot_threads"], datetime.now(timezone.utc),
            )

        await pool.execute("update books set status='completed', updated_at=$2 where id=$1", book_id, datetime.now(timezone.utc))
    except Exception as e:
        logger.exception("Generation failed for book %s", book_id)
        await pool.execute("update books set status='failed', error=$2, updated_at=$3 where id=$1", book_id, str(e), datetime.now(timezone.utc))
    finally:
        # The estimate was already debited as a hold when the book was
        # requested; this reconciles it against the words actually written, so
        # a book that came in under estimate refunds the difference and one
        # that failed part-way only charges for the chapters it produced.
        # Guarded by a one-shot flag: settling twice would refund twice.
        claimed = await pool.execute(
            "update books set settled=true, burned_nc=$2 where id=$1 and settled=false",
            book_id, actual_burn,
        )
        if claimed == "UPDATE 1":
            try:
                fresh = await pool.fetchrow("select title, status from books where id = $1", book_id)
                title = (fresh["title"] if fresh else None) or "book"
                status = fresh["status"] if fresh else None
                if status == "failed":
                    note = f"Settled failed generation of '{title}' ({actual_burn} NC used of {reserved} NC reserved)"
                else:
                    note = f"Settled generation of '{title}' ({actual_burn} NC used of {reserved} NC reserved)"
                await settle_reservation(user_id, reserved, actual_burn, note, related_book_id=book_id)
            except Exception:
                logger.exception("Could not settle credit reservation for book %s", book_id)
