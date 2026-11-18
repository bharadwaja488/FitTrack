import os
import re
import secrets
import ipaddress
from urllib.parse import unquote, urlsplit
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


class ProductionConfigurationError(RuntimeError):
    """Sanitized production configuration issues with no supplied values."""

    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def _environment_integer(name, default):
    value = os.getenv(name)
    if value is None:
        value = default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ProductionConfigurationError((f"{name}: must be an integer.",)) from None


def _redis_storage_issue(storage_uri):
    """Return a value-free explanation when the URL is not authenticated TLS Redis."""
    if storage_uri is None or storage_uri == "":
        return "RATELIMIT_STORAGE_URI: missing; set an authenticated Upstash TCP URL using rediss://."
    if not isinstance(storage_uri, str) or any(char.isspace() for char in storage_uri):
        return "RATELIMIT_STORAGE_URI: invalid; set an authenticated Upstash TCP URL using rediss://."
    try:
        storage = urlsplit(storage_uri)
        hostname = storage.hostname
        port = storage.port
        username = unquote(storage.username or "")
        password = unquote(storage.password or "")
        db_path = storage.path
    except ValueError:
        return "RATELIMIT_STORAGE_URI: invalid URL; use an authenticated rediss:// TCP URL with a valid port."

    # Upstash TCP endpoints use DNS hostnames. Reject percent escapes and IP-style
    # or otherwise malformed labels instead of passing ambiguous hosts to redis-py.
    dns_label = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    valid_hostname = (
        isinstance(hostname, str)
        and len(hostname) <= 253
        and re.fullmatch(rf"{dns_label}(?:\.{dns_label})*", hostname) is not None
    )

    # Upstash's TCP URL supports the default Redis database only. Accept no path
    # (the documented URL form) or the explicit default database `/0`.
    valid_database_path = db_path in ("", "/", "/0")

    valid = (
        storage.scheme.lower() == "rediss"
        and valid_hostname
        and port is not None
        and 1 <= port <= 65535
        and bool(username.strip())
        and bool(password.strip())
        and not storage.query
        and not storage.fragment
        and valid_database_path
    )
    if not valid:
        return (
            "RATELIMIT_STORAGE_URI: must be an authenticated rediss:// URL with hostname and valid port; "
            "query and fragment options are not allowed."
        )
    return None


def validate_security_config(config):
    """Reject unsafe production session settings without revealing their values."""
    if str(config.get("ENVIRONMENT", "development")).lower() not in {"prod", "production"}:
        return
    issues = []

    secret_key = config.get("SECRET_KEY")
    if (not isinstance(secret_key, str) or len(secret_key) < 32
            or secret_key == "replace-with-a-long-random-secret" or len(set(secret_key)) < 10):
        issues.append("SECRET_KEY: provide a non-placeholder, high-entropy value of at least 32 characters.")
    if not config.get("SESSION_COOKIE_SECURE"):
        issues.append("COOKIE_SECURE: set COOKIE_SECURE=true so session cookies are HTTPS-only.")
    if config.get("DEBUG"):
        issues.append("FLASK_DEBUG: set FLASK_DEBUG=false in production.")
    origins = config.get("FRONTEND_ORIGINS", ())
    if not origins:
        issues.append("FRONTEND_ORIGINS: configure at least one public HTTPS frontend origin.")
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
                        issues.append("FRONTEND_ORIGINS: entries must be valid HTTPS origins.")
                        continue
            parsed.port  # Validate malformed ports.
        except ValueError:
            issues.append("FRONTEND_ORIGINS: entries must be valid HTTPS origins.")
            continue
        if (parsed.scheme != "https" or not hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment or is_loopback):
            issues.append("FRONTEND_ORIGINS: entries must be public HTTPS origins without credentials or paths.")
    frontend_url = str(config.get("FRONTEND_URL", "")).rstrip("/")
    if not frontend_url or frontend_url not in origins:
        issues.append("FRONTEND_URL: it must match one of the configured FRONTEND_ORIGINS.")
    required_database = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing_database = [key for key in required_database if not str(config.get(key, "")).strip()]
    if missing_database:
        issues.append(f"{', '.join(missing_database)}: required for production database connections.")
    try:
        port = int(config.get("DB_PORT", 0))
    except (TypeError, ValueError):
        port = 0
    if not 1 <= port <= 65535:
        issues.append("Production requires a valid DB_PORT.")
    for key in ("DB_CONNECT_TIMEOUT", "DB_READ_TIMEOUT", "DB_WRITE_TIMEOUT"):
        try:
            timeout = int(config.get(key, 0))
        except (TypeError, ValueError):
            timeout = 0
        if timeout <= 0:
            issues.append(f"{key}: provide a positive integer timeout in seconds.")
    missing_tls = [key for key in ("DB_SSL_CA", "DB_SSL_VERIFY_CERT", "DB_SSL_VERIFY_IDENTITY")
                   if not config.get(key)]
    if missing_tls:
        issues.append(f"{', '.join(missing_tls)}: configure a CA and verified TLS for database connections.")
    storage_uri = config.get("RATELIMIT_STORAGE_URI", "")
    redis_issue = _redis_storage_issue(storage_uri)
    if redis_issue:
        issues.append(redis_issue)
    try:
        trusted_proxy_hops = int(config.get("TRUSTED_PROXY_HOPS", 0))
    except (TypeError, ValueError):
        trusted_proxy_hops = -1
    if trusted_proxy_hops != 0:
        issues.append("TRUSTED_PROXY_HOPS: set it to 0; X-Forwarded-For and X-Forwarded-Proto are not trusted.")
    mail_fields = (config.get("MAIL_SERVER"), config.get("MAIL_USERNAME"), config.get("MAIL_PASSWORD"))
    if any(mail_fields) and not all(mail_fields):
        missing_mail = [key for key in ("MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD")
                        if not config.get(key)]
        issues.append(f"{', '.join(missing_mail)}: required when password-reset mail is enabled.")
    if config.get("MAIL_ENABLED") and not config.get("MAIL_USE_TLS"):
        issues.append("MAIL_USE_TLS: set MAIL_USE_TLS=true when password-reset mail is enabled.")
    if config.get("GOOGLE_CLIENT_ID") or config.get("GOOGLE_CLIENT_SECRET"):
        if not (config.get("GOOGLE_CLIENT_ID") and config.get("GOOGLE_CLIENT_SECRET")):
            missing_google = [key for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
                              if not config.get(key)]
            issues.append(f"{', '.join(missing_google)}: required when Google OAuth is enabled.")
        try:
            redirect_uri = urlsplit(str(config.get("GOOGLE_REDIRECT_URI", "")))
            public_frontend = urlsplit(frontend_url)
            valid_redirect = (
                redirect_uri.scheme == "https" and redirect_uri.netloc == public_frontend.netloc
                and redirect_uri.path == "/api/auth/google/callback"
                and not redirect_uri.query and not redirect_uri.fragment
            )
        except ValueError:
            valid_redirect = False
        if not valid_redirect:
            issues.append("GOOGLE_REDIRECT_URI: use the public frontend's HTTPS proxied callback URL.")

    if issues:
        raise ProductionConfigurationError(issues)


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
            "RATELIMIT_STORAGE_URI": "rediss://default:configuration-validation-only@rate-limit.example.com:6379/0",
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
    DB_PORT = _environment_integer("DB_PORT", "4000" if IS_PRODUCTION else "3306")
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")
    DB_SSL_VERIFY_CERT = os.getenv("DB_SSL_VERIFY_CERT", "false").lower() == "true"
    DB_SSL_VERIFY_IDENTITY = os.getenv("DB_SSL_VERIFY_IDENTITY", "false").lower() == "true"
    DB_CONNECT_TIMEOUT = _environment_integer("DB_CONNECT_TIMEOUT", "5")
    DB_READ_TIMEOUT = _environment_integer("DB_READ_TIMEOUT", "20")
    DB_WRITE_TIMEOUT = _environment_integer("DB_WRITE_TIMEOUT", "20")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "" if IS_PRODUCTION else "memory://")
    TRUSTED_PROXY_HOPS = _environment_integer("TRUSTED_PROXY_HOPS", "0")
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
    MAIL_PORT = _environment_integer("MAIL_PORT", "587")
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
    PORT = _environment_integer("PORT", "5000")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
