import os
import random
from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/logos")

LOGOS_DIR = Path(__file__).parent.parent / "frontend" / "public" / "logos"
VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


@router.get("")
async def list_logos():
    if not LOGOS_DIR.exists():
        return {"logos": []}
    files = sorted(
        f.name for f in LOGOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS and not f.name.startswith(".")
    )
    return {"logos": files}


@router.get("/random")
async def random_logo():
    if not LOGOS_DIR.exists():
        return {"logo": None}
    files = [
        f.name for f in LOGOS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS and not f.name.startswith(".")
    ]
    return {"logo": random.choice(files) if files else None}
