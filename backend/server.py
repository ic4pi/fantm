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
import payments
import credits
import logos

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=config.get_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(payments.router)
app.include_router(credits.router)
app.include_router(logos.router)


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
    await db.connect()

    absent = config.missing_optional_env()
    if absent:
        logger.warning(
            "Optional provider keys unset (%s) — writer styles routed to those providers "
            "will fall back to the House model.", ", ".join(absent)
        )


@app.on_event("shutdown")
async def shutdown_db_client():
    await db.disconnect()
