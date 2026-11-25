"""
FitTrack - Database-free Google OAuth unit and configuration tests.
Validates provider discovery, production callback URL rules, nonce handling,
OAuth error handling, and account linking logic.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.config import validate_security_config, ProductionConfigurationError
from app.services import account_service
from authlib.integrations.base_client.errors import OAuthError

HIGH_ENTROPY_KEY = "fittrack-production-high-entropy-secret-key-1234567890"


def test_google_provider_disabled_when_credentials_absent():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = False
    client = app.test_client()

    providers = client.get("/api/auth/providers")
    assert providers.status_code == 200
    assert providers.json["data"]["google_enabled"] is False

    google_start = client.get("/api/auth/google")
    assert google_start.status_code == 503
    assert google_start.json["error"]["code"] == "google_not_configured"

    google_cb = client.get("/api/auth/google/callback")
    assert google_cb.status_code == 302
    assert "error=google_not_configured" in google_cb.headers["Location"]


def test_google_provider_enabled_when_credentials_configured():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = True
    app.config["GOOGLE_CLIENT_ID"] = "mock-client-id.apps.googleusercontent.com"
    app.config["GOOGLE_CLIENT_SECRET"] = "mock-client-secret"
    client = app.test_client()

    providers = client.get("/api/auth/providers")
    assert providers.status_code == 200
    assert providers.json["data"]["google_enabled"] is True


def test_incomplete_google_credentials_fails_production_validation():
    base_prod_config = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": HIGH_ENTROPY_KEY,
        "SESSION_COOKIE_SECURE": True,
        "FRONTEND_ORIGINS": ("https://fittrack-pulse.vercel.app",),
        "FRONTEND_URL": "https://fittrack-pulse.vercel.app",
        "DB_HOST": "db.example.com",
        "DB_USER": "fittrack",
        "DB_PASSWORD": "password",
        "DB_NAME": "fittrack",
        "DB_PORT": 4000,
        "DB_SSL_CA": "/etc/ssl/certs/ca.pem",
        "DB_SSL_VERIFY_CERT": True,
        "DB_SSL_VERIFY_IDENTITY": True,
        "DB_CONNECT_TIMEOUT": 5,
        "DB_READ_TIMEOUT": 20,
        "DB_WRITE_TIMEOUT": 20,
        "RATELIMIT_STORAGE_URI": "rediss://default:pwd@rate-limit.example.com:6379/0",
        "TRUSTED_PROXY_HOPS": 0,
        "DEBUG": False,
    }

    # Only client_id
    config_id_only = dict(base_prod_config, GOOGLE_CLIENT_ID="id-only", GOOGLE_CLIENT_SECRET="",
                          GOOGLE_REDIRECT_URI="https://fittrack-pulse.vercel.app/api/auth/google/callback")
    with pytest.raises(ProductionConfigurationError) as exc_info:
        validate_security_config(config_id_only)
    assert any("GOOGLE_CLIENT_SECRET" in issue for issue in exc_info.value.issues)

    # Only client_secret
    config_secret_only = dict(base_prod_config, GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="secret-only",
                              GOOGLE_REDIRECT_URI="https://fittrack-pulse.vercel.app/api/auth/google/callback")
    with pytest.raises(ProductionConfigurationError) as exc_info:
        validate_security_config(config_secret_only)
    assert any("GOOGLE_CLIENT_ID" in issue for issue in exc_info.value.issues)


def test_production_callback_url_validation():
    base_prod_config = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": HIGH_ENTROPY_KEY,
        "SESSION_COOKIE_SECURE": True,
        "FRONTEND_ORIGINS": ("https://fittrack-pulse.vercel.app",),
        "FRONTEND_URL": "https://fittrack-pulse.vercel.app",
        "DB_HOST": "db.example.com",
        "DB_USER": "fittrack",
        "DB_PASSWORD": "password",
        "DB_NAME": "fittrack",
        "DB_PORT": 4000,
        "DB_SSL_CA": "/etc/ssl/certs/ca.pem",
        "DB_SSL_VERIFY_CERT": True,
        "DB_SSL_VERIFY_IDENTITY": True,
        "DB_CONNECT_TIMEOUT": 5,
        "DB_READ_TIMEOUT": 20,
        "DB_WRITE_TIMEOUT": 20,
        "RATELIMIT_STORAGE_URI": "rediss://default:pwd@rate-limit.example.com:6379/0",
        "TRUSTED_PROXY_HOPS": 0,
        "DEBUG": False,
        "GOOGLE_CLIENT_ID": "mock-client-id",
        "GOOGLE_CLIENT_SECRET": "mock-client-secret",
    }

    # Valid: Exact Vercel frontend proxied URL
    valid_config = dict(base_prod_config,
                        GOOGLE_REDIRECT_URI="https://fittrack-pulse.vercel.app/api/auth/google/callback")
    validate_security_config(valid_config)  # Must not raise

    # Invalid: Backend Render direct origin
    invalid_render = dict(base_prod_config,
                          GOOGLE_REDIRECT_URI="https://fittrack-oeh1.onrender.com/api/auth/google/callback")
    with pytest.raises(ProductionConfigurationError) as exc_info:
        validate_security_config(invalid_render)
    assert any("GOOGLE_REDIRECT_URI" in issue for issue in exc_info.value.issues)

    # Invalid: Non-HTTPS URL
    invalid_http = dict(base_prod_config,
                        GOOGLE_REDIRECT_URI="http://fittrack-pulse.vercel.app/api/auth/google/callback")
    with pytest.raises(ProductionConfigurationError) as exc_info:
        validate_security_config(invalid_http)
    assert any("GOOGLE_REDIRECT_URI" in issue for issue in exc_info.value.issues)

    # Invalid: URL with query parameters
    invalid_query = dict(base_prod_config,
                         GOOGLE_REDIRECT_URI="https://fittrack-pulse.vercel.app/api/auth/google/callback?step=1")
    with pytest.raises(ProductionConfigurationError) as exc_info:
        validate_security_config(invalid_query)
    assert any("GOOGLE_REDIRECT_URI" in issue for issue in exc_info.value.issues)


def test_google_login_generates_nonce_and_authorize_redirect():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = True
    app.config["GOOGLE_REDIRECT_URI"] = "https://fittrack-pulse.vercel.app/api/auth/google/callback"

    mock_oauth_client = MagicMock()
    mock_oauth_client.authorize_redirect.return_value = ("redirect_response", 302)

    with patch("app.routes.auth.oauth.create_client", return_value=mock_oauth_client):
        with app.test_client() as client:
            res = client.get("/api/auth/google")
            assert res.status_code == 302
            with client.session_transaction() as sess:
                assert "google_nonce" in sess
                assert len(sess["google_nonce"]) >= 32
            mock_oauth_client.authorize_redirect.assert_called_once()
            call_args = mock_oauth_client.authorize_redirect.call_args
            assert call_args[0][0] == "https://fittrack-pulse.vercel.app/api/auth/google/callback"
            assert "nonce" in call_args[1]


def test_google_callback_rejects_missing_or_stale_nonce():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = True
    app.config["FRONTEND_URL"] = "https://fittrack-pulse.vercel.app"

    with app.test_client() as client:
        # No session nonce set
        res = client.get("/api/auth/google/callback?code=mock_code&state=mock_state")
        assert res.status_code == 302
        assert res.headers["Location"] == "https://fittrack-pulse.vercel.app/login?error=oauth_state"


def test_google_callback_handles_oauth_error_gracefully():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = True
    app.config["FRONTEND_URL"] = "https://fittrack-pulse.vercel.app"

    mock_oauth_client = MagicMock()
    mock_oauth_client.authorize_access_token.side_effect = OAuthError("access_denied", "User denied access")

    with patch("app.routes.auth.oauth.create_client", return_value=mock_oauth_client):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["google_nonce"] = "valid_nonce_12345"

            res = client.get("/api/auth/google/callback?error=access_denied")
            assert res.status_code == 302
            assert res.headers["Location"] == "https://fittrack-pulse.vercel.app/login?error=google_sign_in"


def test_google_callback_successful_login_and_redirects():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = True
    app.config["FRONTEND_URL"] = "https://fittrack-pulse.vercel.app"

    mock_oauth_client = MagicMock()
    mock_oauth_client.authorize_access_token.return_value = {
        "access_token": "mock_token",
        "userinfo": {
            "email": "verified_user@gmail.com",
            "email_verified": True,
            "sub": "google-sub-12345",
            "name": "Verified User",
        }
    }

    # Test user with existing profile -> redirects to /app
    with patch("app.routes.auth.oauth.create_client", return_value=mock_oauth_client):
        with patch("app.services.account_service.google_login",
                   return_value={"account_id": 1, "has_profile": True}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["google_nonce"] = "valid_nonce_12345"

                res = client.get("/api/auth/google/callback?code=code&state=state")
                assert res.status_code == 302
                assert res.headers["Location"] == "https://fittrack-pulse.vercel.app/app"

    # Test user without profile -> redirects to /onboarding
    with patch("app.routes.auth.oauth.create_client", return_value=mock_oauth_client):
        with patch("app.services.account_service.google_login",
                   return_value={"account_id": 2, "has_profile": False}):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["google_nonce"] = "valid_nonce_67890"

                res = client.get("/api/auth/google/callback?code=code&state=state")
                assert res.status_code == 302
                assert res.headers["Location"] == "https://fittrack-pulse.vercel.app/onboarding"


def test_google_login_service_validates_email_verification_and_sub():
    # Unverified email
    with pytest.raises(ValueError, match="Google must verify this email address"):
        account_service.google_login({"email": "unverified@gmail.com", "email_verified": False, "sub": "123"})

    # Missing sub
    with pytest.raises(ValueError, match="Google did not return a verified account identifier"):
        account_service.google_login({"email": "verified@gmail.com", "email_verified": True, "sub": ""})


def test_google_login_account_linking_rejects_cross_account_collision():
    # Simulate an account already linked to a different google_sub
    mock_cur = MagicMock()
    # 1st query: SELECT ... WHERE google_sub=%s -> returns None
    # 2nd query: SELECT ... WHERE email=%s -> returns account with different google_sub
    mock_cur.fetchone.side_effect = [
        None,
        {"account_id": 42, "session_version": 1, "google_sub": "original-google-sub"}
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = (mock_conn, mock_cur)
    mock_ctx.__exit__.return_value = None

    with patch("app.services.account_service.connection", return_value=mock_ctx):
        with pytest.raises(ValueError, match="This email is linked to a different Google account"):
            account_service.google_login({
                "email": "user@gmail.com",
                "email_verified": True,
                "sub": "new-conflicting-sub"
            })
