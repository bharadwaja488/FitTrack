"""Safely remove one uniquely generated browser E2E account and its owned rows."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.database import connection
from app.services.account_service import delete_account

EXPECTED_DATABASE = "fittrack_test_20261116_a91f"
EXPECTED_USER = "ft_test_20261116_a91f"
EXPECTED_ACCOUNT = f"{EXPECTED_USER}@localhost"
EXPECTED_SERVER_HOSTNAME = "DESKTOP-E122APS"
EXPECTED_SERVER_PORT = 3306
CONFIRMATION = "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE"


def _verify_database_identity(cur):
    cur.execute("SELECT DATABASE() AS db, @@hostname AS hostname, @@port AS port, CURRENT_USER() AS account")
    identity = cur.fetchone()
    try:
        valid_port = int(identity["port"]) == EXPECTED_SERVER_PORT
    except (TypeError, ValueError, KeyError):
        valid_port = False
    if (not identity
            or identity.get("db") != EXPECTED_DATABASE
            or identity.get("hostname") != EXPECTED_SERVER_HOSTNAME
            or not valid_port
            or identity.get("account") != EXPECTED_ACCOUNT):
        raise RuntimeError("E2E cleanup refused: connected database or user identity did not match the disposable target.")


def cleanup_one_account(email):
    if (os.getenv("FITTRACK_TEST_DB_NAME") != EXPECTED_DATABASE
            or os.getenv("FITTRACK_TEST_DB_USER") != EXPECTED_USER
            or os.getenv("FITTRACK_TEST_DB_CONFIRM") != CONFIRMATION
            or os.getenv("FITTRACK_TEST_DB_HOST") != "127.0.0.1"):
        raise RuntimeError("E2E cleanup requires the explicitly approved disposable database configuration.")
    config = {
        "DB_NAME": EXPECTED_DATABASE,
        "DB_HOST": "127.0.0.1",
        "DB_USER": EXPECTED_USER,
        "DB_PASSWORD": os.environ["FITTRACK_TEST_DB_PASSWORD"],
    }
    app = create_app()
    app.config.update(config)
    user_id = None
    with app.app_context(), connection() as (_, cur):
        _verify_database_identity(cur)
        cur.execute("SELECT account_id FROM accounts WHERE email=%s", (email,))
        account = cur.fetchone()
        account_id = account["account_id"] if account else None
        if account_id is not None:
            cur.execute("SELECT user_id FROM users WHERE account_id=%s", (account_id,))
            profile = cur.fetchone()
            user_id = profile["user_id"] if profile else None
    if account_id is not None:
        with app.app_context():
            if not delete_account(account_id, os.environ["FITTRACK_E2E_ACCOUNT_PASSWORD"]):
                raise RuntimeError("Could not delete the disposable E2E account.")
    with app.app_context(), connection() as (_, cur):
        _verify_database_identity(cur)
        cur.execute("SELECT COUNT(*) AS count FROM accounts WHERE email=%s", (email,))
        if cur.fetchone()["count"]:
            raise RuntimeError("Disposable E2E account still exists after cleanup.")
        if user_id is not None:
            for table in ("users", "fitness_records", "fitness_goals", "weight_records", "nutrition_records"):
                cur.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE user_id=%s", (user_id,))
                if cur.fetchone()["count"]:
                    raise RuntimeError(f"E2E cleanup left test-owned rows in {table}.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].endswith("@example.com") or not sys.argv[1].startswith("fittrack-e2e-"):
        raise SystemExit("Pass only the unique fittrack-e2e-*@example.com account created by the browser test.")
    cleanup_one_account(sys.argv[1])
