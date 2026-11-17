"""Start the browser-test API only after proving its disposable DB identity."""
import os
import socket
import sys
from pathlib import Path

EXPECTED_DATABASE = "fittrack_test_20261116_a91f"
EXPECTED_DB_HOST = "127.0.0.1"
EXPECTED_DB_PORT = 3306
EXPECTED_DB_USER = "ft_test_20261116_a91f"
EXPECTED_DB_ACCOUNT = f"{EXPECTED_DB_USER}@localhost"
EXPECTED_SERVER_HOSTNAME = "DESKTOP-E122APS"
CONFIRMATION = "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE"


def validate_test_environment(env):
    """Reject missing or mismatched test settings without touching MySQL."""
    expected = {
        "FITTRACK_TEST_DB_NAME": EXPECTED_DATABASE,
        "FITTRACK_TEST_DB_HOST": EXPECTED_DB_HOST,
        "FITTRACK_TEST_DB_USER": EXPECTED_DB_USER,
        "FITTRACK_TEST_DB_CONFIRM": CONFIRMATION,
        "FITTRACK_RUN_DB_TESTS": "1",
    }
    for key, value in expected.items():
        if env.get(key) != value:
            raise RuntimeError(f"E2E server refused: {key} must match the approved disposable test configuration.")
    if not env.get("FITTRACK_TEST_DB_PASSWORD"):
        raise RuntimeError("E2E server refused: provide the test-only database password in FITTRACK_TEST_DB_PASSWORD.")
    return {
        "DB_HOST": EXPECTED_DB_HOST,
        "DB_NAME": EXPECTED_DATABASE,
        "DB_USER": EXPECTED_DB_USER,
        "DB_PASSWORD": env["FITTRACK_TEST_DB_PASSWORD"],
    }


def verify_database_identity(cursor, local_hostname=None):
    cursor.execute("SELECT DATABASE() AS db, @@hostname AS hostname, @@port AS port, CURRENT_USER() AS account")
    identity = cursor.fetchone()
    machine = local_hostname if local_hostname is not None else socket.gethostname()
    try:
        port_matches = int(identity.get("port", 0)) == EXPECTED_DB_PORT if identity else False
    except (TypeError, ValueError):
        port_matches = False
    if (not identity
            or identity.get("db") != EXPECTED_DATABASE
            or identity.get("hostname") != EXPECTED_SERVER_HOSTNAME
            or machine.casefold() != EXPECTED_SERVER_HOSTNAME.casefold()
            or not port_matches
            or identity.get("account") != EXPECTED_DB_ACCOUNT):
        raise RuntimeError("E2E server refused: MySQL database, server, port, or account identity did not match the approved disposable target.")


def main():
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    db_config = validate_test_environment(os.environ)
    os.environ.update(db_config)
    os.environ.update({
        "FITTRACK_ENV": "development",
        "PORT": "5000",
        "FRONTEND_URL": "http://127.0.0.1:5174",
        "FRONTEND_ORIGINS": "http://127.0.0.1:5174,http://localhost:5174",
        "COOKIE_SECURE": "false",
        "FLASK_DEBUG": "false",
    })

    from app import create_app
    from app.database import connection

    app = create_app()
    app.config.update(db_config, PORT=5000)
    try:
        with app.app_context(), connection() as (_, cursor):
            verify_database_identity(cursor)
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("E2E server refused: unable to verify the approved disposable MySQL target.") from None

    print("E2E backend ready on 127.0.0.1:5000 with the verified disposable database.", flush=True)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # The guard messages are deliberately generic and contain no connection secrets.
        print(str(error), file=sys.stderr, flush=True)
        raise SystemExit(1)
