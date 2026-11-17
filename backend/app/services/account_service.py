import smtplib
from email.message import EmailMessage

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from email_validator import EmailNotValidError, validate_email
from flask import current_app, session
from mysql.connector.errors import IntegrityError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..database import connection
from ..auth import establish_session
from .health_service import validate_password

hasher = PasswordHasher()


def normalize_email(raw):
    try:
        return validate_email(str(raw or "").strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError("Enter a valid email address.")


def account_by_id(account_id):
    with connection() as (_, cur):
        cur.execute("SELECT account_id,full_name,email,email_verified,(password_hash IS NOT NULL) AS has_password FROM accounts WHERE account_id=%s", (account_id,))
        account = cur.fetchone()
        if not account:
            return None
        cur.execute("SELECT user_id FROM users WHERE account_id=%s", (account_id,))
        account["has_profile"] = cur.fetchone() is not None
        return account


def register(data):
    full_name = str(data.get("full_name", "")).strip()
    if not full_name or len(full_name) > 100:
        raise ValueError("Full name is required and must be 100 characters or fewer.")
    email = normalize_email(data.get("email"))
    password = validate_password(data.get("password"))
    if data.get("confirm_password") != password:
        raise ValueError("Passwords do not match.")
    try:
        # The unique email index is authoritative. Avoid a lookup/insert race and
        # normalize duplicate and concurrent-duplicate outcomes for the caller.
        with connection() as (conn, cur):
            cur.execute("INSERT INTO accounts (full_name,email,password_hash) VALUES (%s,%s,%s)",
                        (full_name, email, hasher.hash(password)))
            conn.commit()
    except IntegrityError:
        return False
    return True


def login(email_input, password):
    email = normalize_email(email_input)
    with connection() as (_, cur):
        cur.execute("SELECT account_id,password_hash,session_version FROM accounts WHERE email=%s", (email,))
        account = cur.fetchone()
    if not account or not account["password_hash"]:
        return None
    try:
        valid = hasher.verify(account["password_hash"], str(password or ""))
    except (VerifyMismatchError, InvalidHashError, TypeError):
        valid = False
    if not valid:
        return None
    if hasher.check_needs_rehash(account["password_hash"]):
        with connection() as (conn, cur):
            cur.execute("UPDATE accounts SET password_hash=%s WHERE account_id=%s",
                        (hasher.hash(str(password)), account["account_id"]))
            conn.commit()
    establish_session(account["account_id"], account["session_version"])
    return account_by_id(account["account_id"])


def google_login(userinfo):
    email = normalize_email(userinfo.get("email"))
    if userinfo.get("email_verified") not in (True, "true", "True"):
        raise ValueError("Google must verify this email address before it can be used.")
    subject = str(userinfo.get("sub", ""))
    if not subject:
        raise ValueError("Google did not return a verified account identifier.")
    full_name = str(userinfo.get("name") or email.split("@", 1)[0]).strip()[:100]
    with connection() as (conn, cur):
        cur.execute("SELECT account_id,session_version FROM accounts WHERE google_sub=%s FOR UPDATE", (subject,))
        account = cur.fetchone()
        if not account:
            cur.execute("SELECT account_id,session_version,google_sub FROM accounts WHERE email=%s FOR UPDATE", (email,))
            account = cur.fetchone()
            if account:
                if account["google_sub"] and account["google_sub"] != subject:
                    raise ValueError("This email is linked to a different Google account.")
                cur.execute("UPDATE accounts SET google_sub=%s,email_verified=TRUE WHERE account_id=%s",
                            (subject, account["account_id"]))
            else:
                cur.execute("INSERT INTO accounts (full_name,email,google_sub,email_verified) VALUES (%s,%s,%s,TRUE)",
                            (full_name, email, subject))
                account = {"account_id": cur.lastrowid, "session_version": 0}
        conn.commit()
    establish_session(account["account_id"], account.get("session_version", 0))
    return account_by_id(account["account_id"])


def reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="fittrack-password-reset-v1")


def send_password_reset(email):
    # The outward response is always the same, whether the address exists or not.
    with connection() as (_, cur):
        cur.execute("SELECT account_id,session_version FROM accounts WHERE email=%s", (email,))
        account = cur.fetchone()
    if not account:
        return
    token = reset_serializer().dumps({"id": account["account_id"], "version": account["session_version"]})
    link = f"{current_app.config['FRONTEND_URL'].rstrip('/')}/reset-password?token={token}"
    message = EmailMessage()
    message["Subject"] = "Reset your FitTrack password"
    message["From"] = current_app.config["MAIL_USERNAME"]
    message["To"] = email
    message.set_content(f"Use this link within 30 minutes to reset your FitTrack password:\n\n{link}\n\nIf you did not request this, ignore this message.")
    with smtplib.SMTP(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"], timeout=15) as smtp:
        if current_app.config["MAIL_USE_TLS"]:
            smtp.starttls()
        smtp.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
        smtp.send_message(message)


def apply_password_reset(token, password, confirm_password):
    password = validate_password(password)
    if confirm_password != password:
        raise ValueError("Passwords do not match.")
    try:
        payload = reset_serializer().loads(token, max_age=1800)
    except SignatureExpired:
        raise ValueError("This password reset link has expired.")
    except BadSignature:
        raise ValueError("This password reset link is invalid.")
    with connection() as (conn, cur):
        cur.execute("SELECT session_version FROM accounts WHERE account_id=%s FOR UPDATE", (payload.get("id"),))
        account = cur.fetchone()
        if not account or account["session_version"] != payload.get("version"):
            raise ValueError("This password reset link is no longer valid.")
        cur.execute("UPDATE accounts SET password_hash=%s,email_verified=TRUE,session_version=session_version+1 WHERE account_id=%s",
                    (hasher.hash(password), payload["id"]))
        conn.commit()


def change_password(account_id, data):
    current_password = str(data.get("current_password", ""))
    new_password = validate_password(data.get("new_password"))
    if data.get("confirm_password") != new_password:
        raise ValueError("Passwords do not match.")
    with connection() as (conn, cur):
        cur.execute("SELECT password_hash FROM accounts WHERE account_id=%s FOR UPDATE", (account_id,))
        account = cur.fetchone()
        if not account:
            return False
        if account["password_hash"]:
            try:
                valid = hasher.verify(account["password_hash"], current_password)
            except (VerifyMismatchError, InvalidHashError, TypeError):
                valid = False
            if not valid:
                raise ValueError("Current password is incorrect.")
        cur.execute("UPDATE accounts SET password_hash=%s,session_version=session_version+1 WHERE account_id=%s",
                    (hasher.hash(new_password), account_id))
        conn.commit()
    establish_session(account_id, session.get("session_version", 0) + 1)
    return True


def delete_account(account_id, password=""):
    with connection() as (conn, cur):
        cur.execute("SELECT account_id,password_hash FROM accounts WHERE account_id=%s FOR UPDATE", (account_id,))
        account = cur.fetchone()
        if not account:
            return False
        if account["password_hash"]:
            try:
                valid = hasher.verify(account["password_hash"], str(password or ""))
            except (VerifyMismatchError, InvalidHashError, TypeError):
                valid = False
            if not valid:
                raise ValueError("Enter your current password to delete this account.")
        cur.execute("SELECT user_id FROM users WHERE account_id=%s FOR UPDATE", (account_id,))
        profile = cur.fetchone()
        if profile:
            cur.execute("DELETE FROM nutrition_records WHERE user_id=%s", (profile["user_id"],))
            cur.execute("DELETE FROM weight_records WHERE user_id=%s", (profile["user_id"],))
            cur.execute("DELETE FROM fitness_goals WHERE user_id=%s", (profile["user_id"],))
            cur.execute("DELETE FROM fitness_records WHERE user_id=%s", (profile["user_id"],))
            cur.execute("DELETE FROM users WHERE user_id=%s AND account_id=%s", (profile["user_id"], account_id))
        cur.execute("DELETE FROM accounts WHERE account_id=%s", (account_id,))
        conn.commit()
    return True
