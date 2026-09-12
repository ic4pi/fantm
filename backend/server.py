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

from db import db, client
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
    reach Mongo should not read as healthy to a load balancer."""
    try:
        await client.admin.command("ping")
    except Exception:
        logger.exception("Health check failed: database unreachable")
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    # Lockout rows are write-heavy and disposable; without expiry the
    # collection grows forever and never sheds a stale lockout.
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("locked_until", expireAfterSeconds=86400)
    await db.books.create_index("user_id")
    await db.chapters.create_index("book_id")
    # The ledger is queried by user and sorted newest-first on every Store page
    # load; unindexed it is a full collection scan that grows with every
    # transaction the platform has ever written.
    await db.credit_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.payment_transactions.create_index("user_id")

    absent = config.missing_optional_env()
    if absent:
        logger.warning(
            "Optional provider keys unset (%s) — writer styles routed to those providers "
            "will fall back to the House model.", ", ".join(absent)
        )


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
