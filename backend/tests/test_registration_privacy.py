import sys
from pathlib import Path

import pytest
from mysql.connector.errors import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.services import account_service


def test_registration_response_is_same_for_new_and_duplicate_addresses(monkeypatch):
    outcomes = iter((True, False))
    monkeypatch.setattr(account_service, "register", lambda data: next(outcomes))
    client = create_app().test_client()
    csrf = client.get("/api/auth/csrf").json["data"]["csrf_token"]
    payload = {
        "full_name": "Test Person", "email": "person@example.com",
        "password": "StrongPassword123", "confirm_password": "StrongPassword123",
    }

    responses = [client.post("/api/auth/register", json=payload, headers={"X-CSRF-Token": csrf}) for _ in range(2)]

    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json == responses[1].json
    assert "account" not in responses[0].json["data"]


def test_registration_concurrent_unique_conflict_returns_duplicate_outcome(monkeypatch):
    class Cursor:
        def execute(self, *_):
            raise IntegrityError("duplicate unique key")

    class Connection:
        def commit(self):
            raise AssertionError("A duplicate registration must not commit.")

    class ConnectionContext:
        def __enter__(self):
            return Connection(), Cursor()

        def __exit__(self, exc_type, exc, traceback):
            return False

    class FakeHasher:
        @staticmethod
        def hash(password):
            return "test-hash"

    monkeypatch.setattr(account_service, "connection", lambda: ConnectionContext())
    monkeypatch.setattr(account_service, "hasher", FakeHasher())
    result = account_service.register({
        "full_name": "Test Person", "email": "person@example.com",
        "password": "StrongPassword123", "confirm_password": "StrongPassword123",
    })
    assert result is False
