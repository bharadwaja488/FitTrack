from contextlib import contextmanager
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_cleanup_account as cleanup


class FakeApp:
    def __init__(self):
        self.config = {}

    @contextmanager
    def app_context(self):
        yield


class FakeCursor:
    def __init__(self, state, database=cleanup.EXPECTED_DATABASE, hostname=cleanup.EXPECTED_SERVER_HOSTNAME,
                 port=cleanup.EXPECTED_SERVER_PORT, account=cleanup.EXPECTED_ACCOUNT):
        self.state = state
        self.database = database
        self.hostname = hostname
        self.port = port
        self.account = account
        self.row = None

    def execute(self, sql, params=None):
        if "SELECT DATABASE()" in sql:
            self.row = {"db": self.database, "hostname": self.hostname, "port": self.port, "account": self.account}
        elif "SELECT account_id FROM accounts" in sql:
            self.row = {"account_id": 812} if self.state["exists"] else None
        elif "SELECT user_id FROM users" in sql:
            self.row = {"user_id": 912} if self.state["exists"] else None
        elif "COUNT(*) AS count FROM accounts" in sql:
            self.row = {"count": int(self.state["exists"])}
        elif "COUNT(*) AS count FROM" in sql:
            self.row = {"count": 0}
        else:
            raise AssertionError(f"Unexpected cleanup query: {sql}")

    def fetchone(self):
        return self.row


def configure(monkeypatch, *, exists=True):
    for key, value in {
        "FITTRACK_TEST_DB_NAME": cleanup.EXPECTED_DATABASE,
        "FITTRACK_TEST_DB_USER": cleanup.EXPECTED_USER,
        "FITTRACK_TEST_DB_HOST": "127.0.0.1",
        "FITTRACK_TEST_DB_CONFIRM": cleanup.CONFIRMATION,
        "FITTRACK_TEST_DB_PASSWORD": "test-only-secret",
        "FITTRACK_E2E_ACCOUNT_PASSWORD": "test-account-secret",
    }.items():
        monkeypatch.setenv(key, value)
    state = {"exists": exists}
    cursor = FakeCursor(state)

    @contextmanager
    def fake_connection():
        yield object(), cursor

    monkeypatch.setattr(cleanup, "create_app", FakeApp)
    monkeypatch.setattr(cleanup, "connection", fake_connection)
    return state


def test_missing_account_is_idempotently_treated_as_cleaned(monkeypatch):
    configure(monkeypatch, exists=False)
    delete = Mock()
    monkeypatch.setattr(cleanup, "delete_account", delete)

    cleanup.cleanup_one_account("fittrack-e2e-missing@example.com")
    cleanup.cleanup_one_account("fittrack-e2e-missing@example.com")

    delete.assert_not_called()


def test_repeated_cleanup_deletes_only_the_created_account_once(monkeypatch):
    state = configure(monkeypatch, exists=True)
    delete = Mock(side_effect=lambda account_id, _password: state.update(exists=False) or True)
    monkeypatch.setattr(cleanup, "delete_account", delete)

    cleanup.cleanup_one_account("fittrack-e2e-unique@example.com")
    cleanup.cleanup_one_account("fittrack-e2e-unique@example.com")

    delete.assert_called_once_with(812, "test-account-secret")


def test_cleanup_refuses_wrong_database_identity_before_deleting(monkeypatch):
    configure(monkeypatch, exists=True)
    delete = Mock()
    monkeypatch.setattr(cleanup, "delete_account", delete)
    @contextmanager
    def wrong_database():
        cursor = FakeCursor({"exists": True}, database="fittrack")
        yield object(), cursor

    monkeypatch.setattr(cleanup, "connection", wrong_database)
    with pytest.raises(RuntimeError, match="identity did not match"):
        cleanup.cleanup_one_account("fittrack-e2e-unique@example.com")
    delete.assert_not_called()


@pytest.mark.parametrize("identity", [
    {"hostname": "OTHER-HOST"},
    {"port": 3307},
    {"account": "root@localhost"},
])
def test_cleanup_refuses_wrong_server_identity_before_deleting(monkeypatch, identity):
    configure(monkeypatch, exists=True)
    delete = Mock()

    @contextmanager
    def wrong_server():
        cursor = FakeCursor({"exists": True}, **identity)
        yield object(), cursor

    monkeypatch.setattr(cleanup, "connection", wrong_server)
    monkeypatch.setattr(cleanup, "delete_account", delete)
    with pytest.raises(RuntimeError, match="identity did not match"):
        cleanup.cleanup_one_account("fittrack-e2e-unique@example.com")
    delete.assert_not_called()
