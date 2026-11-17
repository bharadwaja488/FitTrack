import secrets

from authlib.integrations.base_client.errors import OAuthError
from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from ..auth import login_required, csrf_token
from ..extensions import oauth, limiter
from ..services import account_service, profile_service
from ..utils.validators import body_json
from ..database import connection

bp = Blueprint("auth", __name__)


@bp.get("/auth/csrf")
def csrf():
    response = jsonify({"data": {"csrf_token": csrf_token()}})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/auth/providers")
def providers():
    return jsonify({"data": {"google_enabled": current_app.config["GOOGLE_ENABLED"],
                              "password_reset_enabled": current_app.config["MAIL_ENABLED"]}})


@bp.post("/auth/register")
@limiter.limit("5 per hour")
def register():
    account_service.register(body_json())
    # Keep the response identical for new and duplicate addresses. The caller
    # signs in after registration; no account details are returned here.
    return jsonify({"data": {"message": "If registration can be completed, sign in to continue. If you already have an account, sign in or reset your password."}}), 202


@bp.post("/auth/login")
@limiter.limit("8 per minute; 30 per hour")
def login():
    data = body_json()
    account = account_service.login(data.get("email"), data.get("password"))
    if not account:
        return jsonify({"error": {"code": "invalid_credentials", "message": "Email or password is incorrect."}}), 401
    return jsonify({"data": {"account": account}})


@bp.post("/auth/logout")
def logout():
    account_id = session.get("account_id")
    try:
        if account_id:
            with connection() as (conn, cur):
                cur.execute("UPDATE accounts SET session_version=session_version+1 WHERE account_id=%s", (account_id,))
                conn.commit()
    finally:
        session.clear()
    return jsonify({"data": {"logged_out": True}})


@bp.get("/auth/me")
@login_required
def me():
    account = dict(session_account())
    account.pop("session_version", None)
    account["profile"] = profile_service.get_profile(account["account_id"])
    account["has_profile"] = account["profile"] is not None
    return jsonify({"data": {"account": account}})


def session_account():
    # The decorator has checked the session; resolve the minimal public account again.
    from flask import g
    return g.account


@bp.get("/auth/google")
def google_login():
    if not current_app.config["GOOGLE_ENABLED"]:
        return jsonify({"error": {"code": "google_not_configured", "message": "Google Sign-In is unavailable until OAuth credentials are configured."}}), 503
    nonce = secrets.token_urlsafe(32)
    session["google_nonce"] = nonce
    client = oauth.create_client("google")
    return client.authorize_redirect(current_app.config["GOOGLE_REDIRECT_URI"], nonce=nonce)


@bp.get("/auth/google/callback")
def google_callback():
    if not current_app.config["GOOGLE_ENABLED"]:
        return redirect(f"{current_app.config['FRONTEND_URL'].rstrip('/')}/login?error=google_not_configured")
    nonce = session.pop("google_nonce", None)
    if not nonce:
        return redirect(f"{current_app.config['FRONTEND_URL'].rstrip('/')}/login?error=oauth_state")
    try:
        token = oauth.create_client("google").authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = oauth.create_client("google").parse_id_token(token, nonce=nonce)
        account = account_service.google_login(userinfo)
    except (OAuthError, ValueError) as error:
        current_app.logger.info("Google sign-in was rejected: %s", error)
        return redirect(f"{current_app.config['FRONTEND_URL'].rstrip('/')}/login?error=google_sign_in")
    target = "/app" if account["has_profile"] else "/onboarding"
    return redirect(f"{current_app.config['FRONTEND_URL'].rstrip('/')}{target}")


@bp.post("/auth/forgot-password")
@limiter.limit("3 per hour")
def forgot_password():
    data = body_json()
    email = account_service.normalize_email(data.get("email"))
    configured = current_app.config["MAIL_ENABLED"]
    if configured:
        try:
            account_service.send_password_reset(email)
        except Exception:
            current_app.logger.exception("Password reset email delivery failed")
            return jsonify({"error": {"code": "mail_unavailable", "message": "Email delivery is temporarily unavailable. Try again later."}}), 503
    return jsonify({"data": {"message": "If an account uses that email, reset instructions will be sent when email delivery is configured.", "mail_configured": configured}})


@bp.post("/auth/reset-password")
@limiter.limit("5 per hour")
def reset_password():
    data = body_json()
    account_service.apply_password_reset(data.get("token", ""), data.get("password"), data.get("confirm_password"))
    session.clear()
    return jsonify({"data": {"password_reset": True}})
