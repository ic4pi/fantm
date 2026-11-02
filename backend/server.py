import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Before anything else imports: every module below reads secrets at import time
# (db, generation, payments), so an unset variable should fail here with a
# message naming it, not further down with a bare KeyError.
import config
config.validate_required_env()

import db
import auth
import books
import credits
import logos

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=config.get_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(credits.router)
app.include_router(logos.router)
if config.payments_enabled():
    import payments
    app.include_router(payments.router)


@app.get("/api/health")
async def health():
    """Liveness plus a real dependency check — a process that is up but can't
    reach Postgres should not read as healthy to a load balancer."""
    try:
        pool = await db.get_pool()
        await pool.fetchval("select 1")
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


@app.on_event("startup")
async def startup():
    # Start even if the database is down (e.g. Supabase paused it): a deploy
    # then still goes live, /api/health reports the database as unreachable,
    # and the first request after the database returns connects normally.
    try:
        await db.connect()
    except Exception:
        logger.exception("Database unreachable at startup; serving anyway and retrying on the next request.")

    absent = config.missing_optional_env()
    if absent:
        logger.warning(
            "Optional provider keys unset (%s) — writer styles routed to those providers "
            "will fall back to the House model.", ", ".join(absent)
        )


@app.on_event("shutdown")
async def shutdown_db_client():
    await db.disconnect()
