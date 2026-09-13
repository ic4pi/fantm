"""The process must refuse to start on an incomplete or unsafe configuration.

Secrets used to be read lazily inside request handlers, or swapped for
placeholders, so a misconfigured deploy booted clean and failed later — 500s on
the first login, checkout sessions posted to Stripe under a fake key.
"""
import pytest

import config

COMPLETE = {
    "DATABASE_URL": "postgresql://postgres:postgres@localhost/fantm",
    "JWT_SECRET": "s" * 48, "GROQ_API_KEY": "gsk_live",
    "STRIPE_SECRET_KEY": "sk_live", "STRIPE_WEBHOOK_SECRET": "whsec_live",
    "CORS_ORIGINS": "https://fantm.ink",
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


@pytest.mark.parametrize("name", sorted(COMPLETE))
def test_every_required_variable_is_enforced(env, name):
    env(**{name: ""})
    with pytest.raises(RuntimeError, match="Refusing to start"):
        config.validate_required_env()


def test_the_error_names_what_is_missing(env):
    env(STRIPE_SECRET_KEY="", GROQ_API_KEY="")
    with pytest.raises(RuntimeError) as excinfo:
        config.validate_required_env()
    assert "STRIPE_SECRET_KEY" in str(excinfo.value)
    assert "GROQ_API_KEY" in str(excinfo.value)


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
