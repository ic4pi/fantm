import os
import random
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/logos")

LOGOS_DIR = Path(__file__).parent.parent / "frontend" / "public" / "logos"
VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def _logo_type(filename: str) -> str:
    """Two layouts live in the same pool: 'icon' marks are a standalone
    glyph meant to be cropped small next to separate wordmark text (the
    nav treatment); 'lockup' marks already have the wordmark baked into
    the art and render as-is, full width, no separate text alongside.
    Convention is a filename prefix so the pool stays name-indifferent —
    anything without a recognized prefix defaults to 'lockup' (the safer
    assumption: showing the whole image never looks broken, whereas
    cropping an unknown image to a corner might)."""
    name = filename.lower()
    if name.startswith("icon_"):
        return "icon"
    return "lockup"


def _collect_logos():
    if not LOGOS_DIR.exists():
        return []
    return sorted(
        f.name for f in LOGOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS and not f.name.startswith(".")
    )


@router.get("")
async def list_logos():
    files = _collect_logos()
    return {"logos": [{"name": f, "type": _logo_type(f)} for f in files]}


@router.get("/random")
async def random_logo():
    files = _collect_logos()
    if not files:
        return {"logo": None, "type": None}
    pick = random.choice(files)
    return {"logo": pick, "type": _logo_type(pick)}

