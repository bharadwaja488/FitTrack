import sys
from pathlib import Path

import pytest
from flask import jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.config import Config, frontend_origins, resolve_environment, validate_security_config


def production_config(**overrides):
    config = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "bK8qV4tM2pX9nR6cL3wF7aH1zD5jS0uE",
        "SESSION_COOKIE_SECURE": True,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "FRONTEND_ORIGINS": ("https://app.example.com",),
        "FRONTEND_URL": "https://app.example.com",
        "DB_HOST": "db.example.com",
        "DB_USER": "fittrack",
        "DB_PASSWORD": "test-placeholder-only",
        "DB_NAME": "fittrack",
        "DB_PORT": 4000,
        "DB_SSL_CA": "/etc/ssl/certs/ca-certificates.crt",
        "DB_SSL_VERIFY_CERT": True,
        "DB_SSL_VERIFY_IDENTITY": True,
        "DB_CONNECT_TIMEOUT": 5,
        "DB_READ_TIMEOUT": 20,
        "DB_WRITE_TIMEOUT": 20,
        "RATELIMIT_STORAGE_URI": "rediss://rate-limit.example.com/0",
        "TRUSTED_PROXY_HOPS": 1,
        "MAIL_ENABLED": False,
        "MAIL_USE_TLS": True,
        "MAIL_SERVER": "",
        "MAIL_USERNAME": "",
        "MAIL_PASSWORD": "",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "GOOGLE_REDIRECT_URI": "",
        "DEBUG": False,
    }
    config.update(overrides)
    return config


def test_production_config_accepts_stable_key_and_secure_cookie():
    validate_security_config(production_config())


@pytest.mark.parametrize("overrides,message", [
    ({"SECRET_KEY": None}, "SECRET_KEY"),
    ({"SECRET_KEY": "short"}, "SECRET_KEY"),
    ({"SECRET_KEY": "replace-with-a-long-random-secret"}, "non-placeholder"),
    ({"SECRET_KEY": "a" * 40}, "high-entropy"),
    ({"SESSION_COOKIE_SECURE": False}, "COOKIE_SECURE=true"),
    ({"DEBUG": True}, "FLASK_DEBUG=false"),
    ({"DB_PASSWORD": ""}, "DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME"),
    ({"DB_PORT": "not-a-port"}, "valid DB_PORT"),
    ({"DB_SSL_VERIFY_IDENTITY": False}, "verified TLS"),
    ({"RATELIMIT_STORAGE_URI": "memory://"}, "shared TLS Redis"),
    ({"RATELIMIT_STORAGE_URI": "redis://cache.example.com/0"}, "shared TLS Redis"),
    ({"RATELIMIT_STORAGE_URI": "memcached://cache.example.com:11211"}, "shared TLS Redis"),
    ({"RATELIMIT_STORAGE_URI": "rediss:///0"}, "shared TLS Redis"),
    ({"TRUSTED_PROXY_HOPS": 0}, "TRUSTED_PROXY_HOPS"),
    ({"GOOGLE_CLIENT_ID": "client-id"}, "both client credentials"),
    ({"GOOGLE_CLIENT_ID": "client-id", "GOOGLE_CLIENT_SECRET": "secret",
      "GOOGLE_REDIRECT_URI": "https://api.example.com/api/auth/google/callback"}, "proxied callback URL"),
    ({"MAIL_ENABLED": True, "MAIL_USE_TLS": False}, "MAIL_USE_TLS=true"),
    ({"MAIL_SERVER": "smtp.example.com"}, "MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD together"),
])
def test_production_config_fails_closed_without_required_settings(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        validate_security_config(production_config(**overrides))


def test_development_config_does_not_require_production_overrides():
    validate_security_config({"ENVIRONMENT": "development", "SECRET_KEY": None, "SESSION_COOKIE_SECURE": False})


def test_render_defaults_to_production_when_fittrack_environment_is_missing(monkeypatch):
    monkeypatch.delenv("FITTRACK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert resolve_environment() == "production"


def test_local_environment_defaults_to_development_without_render_marker(monkeypatch):
    monkeypatch.delenv("FITTRACK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert resolve_environment() == "development"


def test_api_responses_are_never_cacheable():
    app = create_app()
    app.add_url_rule("/api/cache-policy-test", view_func=lambda: jsonify({"ok": True}))
    response = app.test_client().get("/api/cache-policy-test")
    assert response.headers["Cache-Control"] == "no-store"


def test_development_origins_include_the_configured_vite_port():
    origins = frontend_origins("development", "http://localhost:5174", "")
    assert "http://localhost:5174" in origins
    assert "http://127.0.0.1:5174" in origins


@pytest.mark.parametrize("configured", [
    "",
    "http://app.example.com",
    "https://localhost:8443",
    "https://localhost.",
    "https://127.0.0.1",
    "https://[::ffff:127.0.0.1]",
    "https://user:password@app.example.com",
    "https://app.example.com/path",
    "https://app.example.com?query=1",
    "https://*",
    "https://bad host.example",
])
def test_production_origins_fail_closed(configured):
    with pytest.raises(RuntimeError, match="FRONTEND_ORIGINS"):
        frontend_origins("production", "http://localhost:5174", configured)


def test_production_origins_use_only_explicit_public_https_origins():
    origins = frontend_origins("production", "http://localhost:5174", "https://app.example.com")
    assert origins == ("https://app.example.com",)
    validate_security_config(production_config(FRONTEND_ORIGINS=origins, FRONTEND_URL=origins[0]))


def test_configured_proxy_hop_is_applied_before_rate_limit_ip_lookup(monkeypatch):
    monkeypatch.setattr(Config, "TRUSTED_PROXY_HOPS", 1)
    app = create_app()
    app.add_url_rule("/proxy-test", view_func=lambda: jsonify({"remote_addr": request.remote_addr}))
    response = app.test_client().get("/proxy-test", headers={"X-Forwarded-For": "203.0.113.10"})
    assert response.json["remote_addr"] == "203.0.113.10"


def test_application_startup_validates_production_settings(monkeypatch):
    monkeypatch.setattr(Config, "ENVIRONMENT", "production")
    monkeypatch.setattr(Config, "SECRET_KEY", None)
    monkeypatch.setattr(Config, "SESSION_COOKIE_SECURE", False)
    with pytest.raises(RuntimeError, match="SECRET_KEY") as error:
        create_app()
    assert "private-value" not in str(error.value)
