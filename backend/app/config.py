import os
import re
import secrets
import ipaddress
from urllib.parse import urlsplit
from dotenv import load_dotenv


def resolve_environment():
    """Default hosted Render services to production even when app mode is omitted."""
    explicit_environment = os.getenv("FITTRACK_ENV")
    if explicit_environment:
        return explicit_environment.strip().lower()
    if os.getenv("RENDER", "").strip().lower() == "true":
        return "production"
    return os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()


_configured_environment = resolve_environment()
if _configured_environment not in {"prod", "production"}:
    load_dotenv()


def validate_security_config(config):
    """Reject unsafe production session settings without revealing their values."""
    if str(config.get("ENVIRONMENT", "development")).lower() not in {"prod", "production"}:
        return
    secret_key = config.get("SECRET_KEY")
    if (not isinstance(secret_key, str) or len(secret_key) < 32
            or secret_key == "replace-with-a-long-random-secret" or len(set(secret_key)) < 10):
        raise RuntimeError("Production requires a non-placeholder, high-entropy SECRET_KEY of at least 32 characters.")
    if not config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError("Production requires COOKIE_SECURE=true so session cookies are HTTPS-only.")
    if config.get("DEBUG"):
        raise RuntimeError("Production requires FLASK_DEBUG=false.")
    origins = config.get("FRONTEND_ORIGINS", ())
    if not origins:
        raise RuntimeError("Production requires FRONTEND_ORIGINS with at least one HTTPS frontend origin.")
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            hostname = parsed.hostname or ""
            normalized_hostname = hostname.lower().rstrip(".")
            is_loopback = normalized_hostname == "localhost" or normalized_hostname.endswith(".localhost")
            if hostname:
                try:
                    address = ipaddress.ip_address(hostname)
                    is_loopback = is_loopback or address.is_loopback or bool(
                        address.ipv4_mapped and address.ipv4_mapped.is_loopback
                    )
                except ValueError:
                    dns_name = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                    if not re.fullmatch(rf"{dns_name}(?:\.{dns_name})*", hostname):
                        raise RuntimeError("Production FRONTEND_ORIGINS must contain valid HTTPS origins only.") from None
            parsed.port  # Validate malformed ports.
        except ValueError:
            raise RuntimeError("Production FRONTEND_ORIGINS must contain valid HTTPS origins only.") from None
        if (parsed.scheme != "https" or not hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment or is_loopback):
            raise RuntimeError("Production FRONTEND_ORIGINS must contain valid public HTTPS origins only.")
    frontend_url = str(config.get("FRONTEND_URL", "")).rstrip("/")
    if not frontend_url or frontend_url not in origins:
        raise RuntimeError("Production FRONTEND_URL must match one of the configured FRONTEND_ORIGINS.")
    required_database = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    if any(not str(config.get(key, "")).strip() for key in required_database):
        raise RuntimeError("Production requires DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME.")
    try:
        port = int(config.get("DB_PORT", 0))
    except (TypeError, ValueError):
        port = 0
    if not 1 <= port <= 65535:
        raise RuntimeError("Production requires a valid DB_PORT.")
    try:
        timeouts = [int(config.get(key, 0)) for key in ("DB_CONNECT_TIMEOUT", "DB_READ_TIMEOUT", "DB_WRITE_TIMEOUT")]
    except (TypeError, ValueError):
        timeouts = [0]
    if any(timeout <= 0 for timeout in timeouts):
        raise RuntimeError("Production requires positive database connection, read, and write timeouts.")
    if not config.get("DB_SSL_CA") or not config.get("DB_SSL_VERIFY_CERT") or not config.get("DB_SSL_VERIFY_IDENTITY"):
        raise RuntimeError("Production requires a CA and verified TLS for database connections.")
    storage_uri = str(config.get("RATELIMIT_STORAGE_URI", ""))
    try:
        storage = urlsplit(storage_uri)
        storage.port  # Validate malformed ports without exposing the URI.
        valid_rate_limit_storage = (
            storage.scheme.lower() == "rediss"
            and bool(storage.hostname)
            and not storage.query
            and not storage.fragment
        )
    except ValueError:
        valid_rate_limit_storage = False
    if not valid_rate_limit_storage:
        raise RuntimeError("Production requires a shared TLS Redis RATELIMIT_STORAGE_URI using rediss://.")
    try:
        trusted_proxy_hops = int(config.get("TRUSTED_PROXY_HOPS", 0))
    except (TypeError, ValueError):
        trusted_proxy_hops = -1
    if trusted_proxy_hops != 0:
        raise RuntimeError(
            "Production requires TRUSTED_PROXY_HOPS=0; X-Forwarded-For and X-Forwarded-Proto are not trusted."
        )
    mail_fields = (config.get("MAIL_SERVER"), config.get("MAIL_USERNAME"), config.get("MAIL_PASSWORD"))
    if any(mail_fields) and not all(mail_fields):
        raise RuntimeError("Production mail configuration requires MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD together.")
    if config.get("MAIL_ENABLED") and not config.get("MAIL_USE_TLS"):
        raise RuntimeError("Production password-reset SMTP requires MAIL_USE_TLS=true.")
    if config.get("GOOGLE_CLIENT_ID") or config.get("GOOGLE_CLIENT_SECRET"):
        if not (config.get("GOOGLE_CLIENT_ID") and config.get("GOOGLE_CLIENT_SECRET")):
            raise RuntimeError("Production Google OAuth requires both client credentials.")
        redirect_uri = urlsplit(str(config.get("GOOGLE_REDIRECT_URI", "")))
        public_frontend = urlsplit(frontend_url)
        if (redirect_uri.scheme != "https" or redirect_uri.netloc != public_frontend.netloc
                or redirect_uri.path != "/api/auth/google/callback" or redirect_uri.query or redirect_uri.fragment):
            raise RuntimeError("Production GOOGLE_REDIRECT_URI must use the public frontend's proxied callback URL.")


def frontend_origins(environment, frontend_url, configured_origins):
    """Build an explicit origin allowlist; production never receives local defaults."""
    configured = [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
    if environment in {"prod", "production"}:
        origins = tuple(dict.fromkeys(configured))
        validate_security_config({
            "ENVIRONMENT": environment,
            "SECRET_KEY": "configuration-validation-key-long-enough",
            "SESSION_COOKIE_SECURE": True,
            "FRONTEND_ORIGINS": origins,
            "FRONTEND_URL": origins[0] if origins else "",
            "DB_HOST": "db.example.com",
            "DB_USER": "fittrack",
            "DB_PASSWORD": "configuration-validation-only",
            "DB_NAME": "fittrack",
            "DB_PORT": 4000,
            "DB_SSL_CA": "/etc/ssl/certs/ca-certificates.crt",
            "DB_SSL_VERIFY_CERT": True,
            "DB_SSL_VERIFY_IDENTITY": True,
            "DB_CONNECT_TIMEOUT": 5,
            "DB_READ_TIMEOUT": 20,
            "DB_WRITE_TIMEOUT": 20,
            "RATELIMIT_STORAGE_URI": "rediss://rate-limit.example.com/0",
            "TRUSTED_PROXY_HOPS": 0,
            "MAIL_ENABLED": False,
            "MAIL_SERVER": "",
            "MAIL_USERNAME": "",
            "MAIL_PASSWORD": "",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "DEBUG": False,
        })
        return origins
    defaults = ("http://localhost:5174", "http://127.0.0.1:5174")
    return tuple(dict.fromkeys((*defaults, frontend_url.rstrip("/"), *configured)))


class Config:
    ENVIRONMENT = resolve_environment()
    IS_PRODUCTION = ENVIRONMENT in {"prod", "production"}
    DB_HOST = os.getenv("DB_HOST")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")
    DB_PORT = int(os.getenv("DB_PORT", "4000" if IS_PRODUCTION else "3306"))
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")
    DB_SSL_VERIFY_CERT = os.getenv("DB_SSL_VERIFY_CERT", "false").lower() == "true"
    DB_SSL_VERIFY_IDENTITY = os.getenv("DB_SSL_VERIFY_IDENTITY", "false").lower() == "true"
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
    DB_READ_TIMEOUT = int(os.getenv("DB_READ_TIMEOUT", "20"))
    DB_WRITE_TIMEOUT = int(os.getenv("DB_WRITE_TIMEOUT", "20"))
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
    RENDER_SERVICE = os.getenv("RENDER", "").strip().lower() == "true"
    # Local development remains convenient; production must supply a stable key.
    SECRET_KEY = os.getenv("SECRET_KEY") or (None if IS_PRODUCTION else secrets.token_hex(32))
    _FRONTEND_URL = os.getenv("FRONTEND_URL") or os.getenv("FRONTEND_ORIGIN")
    FRONTEND_ORIGINS = frontend_origins(ENVIRONMENT, _FRONTEND_URL or "http://localhost:5174", os.getenv("FRONTEND_ORIGINS", ""))
    FRONTEND_URL = (_FRONTEND_URL or FRONTEND_ORIGINS[0]) if IS_PRODUCTION else (_FRONTEND_URL or "http://localhost:5174")
    FRONTEND_ORIGIN = FRONTEND_URL.rstrip("/")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/api/auth/google/callback")
    GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_ENABLED = bool(MAIL_SERVER and MAIL_USERNAME and MAIL_PASSWORD)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    SESSION_COOKIE_DOMAIN = None
    SESSION_COOKIE_PATH = "/"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    SESSION_REFRESH_EACH_REQUEST = False
    MAX_CONTENT_LENGTH = 1024 * 1024
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
