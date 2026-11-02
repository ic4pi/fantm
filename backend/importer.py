"""Turn an author's existing notes (a .txt, .md, .docx or .pdf) into the
create-book form's fields, for the author to review before generating.

Extraction only ever fills in what the document actually says. Every field
is optional, so a field the document doesn't cover comes back empty rather
than invented. The result is clamped to CreateBookIn's own limits so the form
can submit it as-is.
"""
import io
import logging
import re
import zipfile
from xml.etree import ElementTree

from generation import _chat, _parse_json_loose

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
CHUNK_CHARS = 15000
MAX_CHUNKS = 3
SUPPORTED = (".txt", ".md", ".docx", ".pdf")

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class UnreadableDocument(ValueError):
    pass


def _docx_text(data: bytes) -> str:
    """Paragraphs and tables from word/document.xml, without a docx
    dependency: a .docx is a zip, and its body is plain WordprocessingML.
    Table rows come out as "cell | cell" so tabular notes stay tabular."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as e:
        raise UnreadableDocument("That .docx file couldn't be opened.") from e

    def para_text(p):
        out = []
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                out.append(node.text)
            elif node.tag == f"{_W}tab":
                out.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                out.append("\n")
        return "".join(out)

    body = root.find(f"{_W}body")
    lines = []
    for el in (body if body is not None else []):
        if el.tag == f"{_W}p":
            lines.append(para_text(el))
        elif el.tag == f"{_W}tbl":
            for tr in el.iter(f"{_W}tr"):
                cells = [" ".join(para_text(p) for p in tc.iter(f"{_W}p")).strip() for tc in tr.iter(f"{_W}tc")]
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise UnreadableDocument("That PDF couldn't be read.") from e


def read_document(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace")
    elif name.endswith(".docx"):
        text = _docx_text(data)
    elif name.endswith(".pdf"):
        text = _pdf_text(data)
    else:
        raise UnreadableDocument(f"Unsupported file type. Use one of: {', '.join(SUPPORTED)}.")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise UnreadableDocument("No text found in that file. (A scanned PDF is an image, not text.)")
    return text


EXTRACT_SYSTEM = (
    "You extract a book author's planning notes into structured fields. Respond ONLY with valid raw JSON, "
    "no markdown fences, no commentary. Copy what the notes say — do not invent, embellish or fill gaps. "
    "Any field the notes don't cover stays empty (\"\" or [])."
)

EXTRACT_SHAPE = """{
  "book_type": "novel | memoir | biography, or \\"\\" if unclear",
  "title": "",
  "prompt": "the core premise / pitch of the book",
  "genre": "", "tone": "",
  "subject": "memoir/biography only: whose life",
  "period": "memoir/biography only: years covered",
  "setting": "", "backstory": "",
  "themes": ["short theme"],
  "pov": "first_person | third_limited | third_omniscient | second_person, or \\"\\"",
  "style_notes": "how the author wants it written",
  "influences": "books or authors named as influences",
  "special_instructions": "any other instruction to the writer that fits no field above",
  "chapter_outline": "chapter-by-chapter plan, one line per chapter, if the notes have one",
  "timeline": "dated or ordered sequence of events, if the notes have one",
  "world_rules": ["special rule of how this world works"],
  "characters": [{"name": "", "role": "", "description": ""}],
  "tables": [{"name": "e.g. Schedule", "columns": ["Col A", "Col B"], "rows": [{"Col A": "", "Col B": ""}]}]
}"""


def _extract_chunk(chunk: str, part: int, parts: int) -> dict:
    where = f" (part {part} of {parts} of the document)" if parts > 1 else ""
    user = (
        f"Author's notes{where}:\n---\n{chunk}\n---\n\n"
        "Extract them into JSON with exactly this shape. Put any tabular data (schedules, results, rosters, "
        "opponents, dated events) into \"tables\" with its real column names.\n" + EXTRACT_SHAPE
    )
    raw = _chat([{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": user}], max_tokens=4000, temperature=0.1)
    return _parse_json_loose(raw)


def _s(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def merge_extractions(parts: list[dict]) -> dict:
    """Combine per-chunk results and clamp everything to CreateBookIn's
    limits. Short fields take the first non-empty value; long text fields
    join every part's text; lists dedupe; tables with the same name merge."""
    out = {k: "" for k in ("book_type", "title", "prompt", "genre", "tone", "subject", "period", "pov")}
    long_text = {"setting": [], "backstory": [], "style_notes": [], "influences": [], "special_instructions": [],
                 "chapter_outline": [], "timeline": []}
    themes, rules, characters, tables = [], [], {}, {}

    for p in parts:
        for k in out:
            if not out[k] and _s(p.get(k)):
                out[k] = _s(p.get(k))
        for k in long_text:
            if _s(p.get(k)):
                long_text[k].append(_s(p.get(k)))
        for t in p.get("themes") or []:
            if _s(t) and _s(t).lower() not in (x.lower() for x in themes):
                themes.append(_s(t))
        for r in p.get("world_rules") or []:
            if _s(r) and _s(r).lower() not in (x.lower() for x in rules):
                rules.append(_s(r))
        for c in p.get("characters") or []:
            if not isinstance(c, dict) or not _s(c.get("name")):
                continue
            key = _s(c["name"]).lower()
            prev = characters.setdefault(key, {"name": _s(c["name"]), "role": "", "description": ""})
            prev["role"] = prev["role"] or _s(c.get("role"))
            prev["description"] = prev["description"] or _s(c.get("description"))
        for t in p.get("tables") or []:
            if not isinstance(t, dict) or not _s(t.get("name")):
                continue
            key = _s(t["name"]).lower()
            prev = tables.setdefault(key, {"name": _s(t["name"]), "columns": [], "rows": []})
            for col in t.get("columns") or []:
                if _s(col) and _s(col) not in prev["columns"]:
                    prev["columns"].append(_s(col))
            for row in t.get("rows") or []:
                if isinstance(row, dict):
                    prev["rows"].append({str(k).strip(): str(v) for k, v in row.items()})

    if out["book_type"] not in ("novel", "memoir", "biography"):
        out["book_type"] = ""
    if out["pov"] not in ("first_person", "third_limited", "third_omniscient", "second_person"):
        out["pov"] = ""
    limits = {"title": 200, "prompt": 4000, "subject": 200, "period": 200, "genre": 200, "tone": 200}
    for k, n in limits.items():
        out[k] = out[k][:n]
    long_limits = {"setting": 2000, "backstory": 3000, "style_notes": 2000, "influences": 500,
                   "special_instructions": 4000, "chapter_outline": 6000, "timeline": 6000}
    for k, n in long_limits.items():
        out[k] = "\n\n".join(long_text[k])[:n]
    out["themes"] = themes[:15]
    out["world_rules"] = rules[:30]
    out["characters"] = [
        {"name": c["name"][:100], "role": c["role"][:100], "description": c["description"][:500]}
        for c in list(characters.values())[:12]
    ]
    out["tables"] = [
        {"name": t["name"][:100], "columns": t["columns"][:20], "rows": t["rows"][:500]}
        for t in list(tables.values())[:20]
    ]
    return out


def extract_bible(text: str) -> dict:
    chunks = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)]
    read = chunks[:MAX_CHUNKS]
    parts = []
    for n, chunk in enumerate(read, start=1):
        try:
            parts.append(_extract_chunk(chunk, n, len(read)))
        except Exception:
            logger.exception("Extraction failed on part %s of %s", n, len(read))
    if not parts:
        raise RuntimeError("Couldn't extract anything from that document. Please try again.")
    result = merge_extractions(parts)
    result["chars_read"] = sum(len(c) for c in read)
    result["chars_total"] = len(text)
    return result
