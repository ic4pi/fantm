"""Startup configuration guard.

Every secret this app needs used to be read lazily — os.environ[...] inside a
request handler, or an `or "placeholder"` fallback. A deploy missing a variable
therefore booted clean and failed later: 500s on the first login, or checkout
sessions posted to Stripe with a fake key. This module turns all of that into
one loud failure at import time, before the process starts serving.
"""
import os

REQUIRED_ENV = {
    "DATABASE_URL": "Postgres connection string (Supabase: Project Settings -> Database -> Connection string).",
    "JWT_SECRET": "Secret used to sign access and refresh tokens.",
    "GROQ_API_KEY": "Groq key for the House model (outlines, continuity, free-tier prose).",
    "STRIPE_SECRET_KEY": "Stripe secret key used to create checkout sessions.",
    "STRIPE_WEBHOOK_SECRET": "Stripe signing secret used to verify webhook deliveries.",
    "CORS_ORIGINS": "Comma-separated list of allowed browser origins.",
}

# Styles routed to these providers need their key, but only if such a style is
# actually reachable — chat_providers raises a clear error at call time, so
# these stay advisory rather than fatal.
OPTIONAL_ENV = ("OPENROUTER_API_KEY", "VENICE_API_KEY", "ANTHROPIC_API_KEY")

INSECURE_JWT_SECRETS = {"secret", "changeme", "change-me", "dev", "development", "test", "jwt_secret"}


def validate_required_env():
    """Raise if anything required is missing or obviously unsafe."""
    missing = [name for name in REQUIRED_ENV if not (os.environ.get(name) or "").strip()]
    if missing:
        details = "\n".join(f"  - {name}: {REQUIRED_ENV[name]}" for name in sorted(missing))
        raise RuntimeError(
            f"Refusing to start — {len(missing)} required environment variable(s) are unset:\n{details}"
        )

    secret = os.environ["JWT_SECRET"].strip()
    if len(secret) < 32 or secret.lower() in INSECURE_JWT_SECRETS:
        raise RuntimeError(
            "Refusing to start — JWT_SECRET must be a random value of at least 32 characters. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    if get_cors_origins() == ["*"]:
        raise RuntimeError(
            "Refusing to start — CORS_ORIGINS is '*' while auth runs on credentialed cookies. "
            "Set it to the explicit browser origin(s), e.g. CORS_ORIGINS=https://fantm.ink"
        )


def get_cors_origins() -> list:
    raw = os.environ.get("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def missing_optional_env() -> list:
    return [name for name in OPTIONAL_ENV if not (os.environ.get(name) or "").strip()]
