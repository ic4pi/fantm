"""The process must refuse to start on an incomplete or unsafe configuration.

Secrets used to be read lazily inside request handlers, or swapped for
placeholders, so a misconfigured deploy booted clean and failed later — 500s on
the first login, checkout sessions posted to Stripe under a fake key.
"""
import pytest

import config

REQUIRED = {
    "DATABASE_URL": "postgresql://postgres:postgres@localhost/fantm",
    "JWT_SECRET": "s" * 48,
    "CORS_ORIGINS": "https://fantm.ink",
}

COMPLETE_HOUSE = {"GROQ_API_KEY": "gsk_live", "OPENROUTER_API_KEY": ""}

COMPLETE = {
    **REQUIRED,
    **COMPLETE_HOUSE,
    "STRIPE_SECRET_KEY": "sk_live", "STRIPE_WEBHOOK_SECRET": "whsec_live",
}


@pytest.fixture
def env(monkeypatch):
    def apply(**overrides):
        for name, value in {**COMPLETE, **overrides}.items():
            monkeypatch.setenv(name, value)
    return apply


def test_a_complete_configuration_starts(env):
    env()
    config.validate_required_env()


@pytest.mark.parametrize("name", sorted(REQUIRED))
def test_every_required_variable_is_enforced(env, name):
    env(**{name: ""})
    with pytest.raises(RuntimeError, match="Refusing to start"):
        config.validate_required_env()


def test_the_error_names_what_is_missing(env):
    env(JWT_SECRET="", DATABASE_URL="")
    with pytest.raises(RuntimeError) as excinfo:
        config.validate_required_env()
    assert "JWT_SECRET" in str(excinfo.value)
    assert "DATABASE_URL" in str(excinfo.value)


def test_house_model_runs_on_openrouter_when_groq_is_absent(env):
    env(GROQ_API_KEY="", OPENROUTER_API_KEY="sk-or-live")
    config.validate_required_env()


def test_startup_is_refused_with_neither_groq_nor_openrouter(env):
    env(GROQ_API_KEY="", OPENROUTER_API_KEY="")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY or OPENROUTER_API_KEY"):
        config.validate_required_env()


def test_stripe_is_optional_so_books_can_generate_without_checkout(env):
    env(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
    config.validate_required_env()
    assert config.payments_enabled() is False


def test_a_half_set_stripe_config_is_rejected(env):
    env(STRIPE_WEBHOOK_SECRET="")
    with pytest.raises(RuntimeError, match="Stripe"):
        config.validate_required_env()


@pytest.mark.parametrize("secret", ["changeme", "secret", "dev", "short", "a" * 31])
def test_a_weak_jwt_secret_is_rejected(env, secret):
    env(JWT_SECRET=secret)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        config.validate_required_env()


def test_wildcard_cors_is_rejected_because_auth_uses_cookies(env):
    env(CORS_ORIGINS="*")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        config.validate_required_env()


def test_cors_origins_are_split_and_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://fantm.ink , https://www.fantm.ink ,, ")
    assert config.get_cors_origins() == ["https://fantm.ink", "https://www.fantm.ink"]


def test_provider_keys_are_advisory_not_fatal(env, monkeypatch):
    env()
    for name in config.OPTIONAL_ENV:
        monkeypatch.delenv(name, raising=False)
    config.validate_required_env()
    assert set(config.missing_optional_env()) == set(config.OPTIONAL_ENV)


def test_startup_migrations_restore_a_missing_column(client):
    # A database that predates migration 005 gets books.bible on boot.
    async def drop_then_migrate():
        import db
        pool = await db.get_pool()
        await pool.execute("alter table books drop column if exists bible")
        await db.apply_migrations()
        return await pool.fetchval(
            "select count(*) from information_schema.columns where table_name='books' and column_name='bible'")
    assert client.portal.call(drop_then_migrate) == 1


def test_the_api_starts_and_reports_degraded_when_the_database_is_down(client, monkeypatch):
    import db
    import server
    live_pool = db.pool
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:1/unreachable")
    db.pool = None
    try:
        client.portal.call(server.startup)  # must not raise
        body = client.get("/api/health").json()
        assert body["status"] == "degraded" and body["database"] == "unreachable"
        assert body["error"]  # names the exception class, nothing more
    finally:
        db.pool = live_pool
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}
