from functools import wraps
import hmac
import secrets

from flask import current_app, g, jsonify, request, session

from .database import connection


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        account_id = session.get("account_id")
        session_version = session.get("session_version")
        if not account_id or session_version is None:
            return jsonify({"error": {"code": "authentication_required", "message": "Sign in to continue."}}), 401
        with connection() as (_, cur):
            cur.execute("SELECT account_id, full_name, email, email_verified, session_version,(password_hash IS NOT NULL) AS has_password FROM accounts WHERE account_id=%s", (account_id,))
            account = cur.fetchone()
        if not account or account["session_version"] != session_version:
            session.clear()
            return jsonify({"error": {"code": "session_expired", "message": "Your session has expired. Sign in again."}}), 401
        g.account = account
        return view(*args, **kwargs)
    return wrapped


def establish_session(account_id, session_version=0):
    session.clear()
    session.permanent = True
    session["account_id"] = int(account_id)
    session["session_version"] = int(session_version)
    session["csrf_token"] = secrets.token_urlsafe(32)


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_valid():
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
