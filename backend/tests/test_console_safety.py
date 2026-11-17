import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "0", "501", "bad", "9" * 5000])
def test_console_weight_reader_rejects_nonfinite_and_out_of_range_values(monkeypatch, raw):
    monkeypatch.setattr("builtins.input", lambda _: raw)
    with pytest.raises(ValueError):
        main._read_number("Weight: ", "Weight", 1, 500)


@pytest.mark.parametrize("raw,expected", [("1.7", 1.7), ("500", 500.0), ("0", 0.0)])
def test_console_number_reader_accepts_supported_finite_values(monkeypatch, raw, expected):
    monkeypatch.setattr("builtins.input", lambda _: raw)
    assert main._read_number("Value: ", "Value", 0, 500) == expected


def test_console_rejects_nonfinite_user_input_before_connecting(monkeypatch, capsys):
    answers = iter(("Athlete", "30", "female", "NaN"))
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(main, "create_connection", lambda: pytest.fail("Invalid input must not access the database."))

    main.add_user()

    assert "Height must be a finite number." in capsys.readouterr().out


class FakeCursor:
    def __init__(self, account_id, has_account_column=True, fail_delete_user=False):
        self.account_id = account_id
        self.account_id_after_initial_check = None
        self.account_check_count = 0
        self.has_account_column = has_account_column
        self.fail_delete_user = fail_delete_user
        self.statements = []
        self.result = None

    def execute(self, query, params=()):
        self.statements.append(query)
        if query.startswith("SELECT * FROM users"):
            self.result = (9, "Web user", 30, "female", 1.7, 70, 24, 2000)
        elif query.startswith("SHOW COLUMNS"):
            self.result = ("account_id",) if self.has_account_column else None
        elif query.startswith("SELECT account_id"):
            self.account_check_count += 1
            if "FOR UPDATE" in query:
                value = self.account_id_after_initial_check
                self.result = (self.account_id if value is None else value,)
            else:
                self.result = (self.account_id,)
        elif query.startswith("SELECT user_id FROM users"):
            self.result = (9,)
        else:
            if self.fail_delete_user and query.startswith("DELETE FROM users"):
                raise RuntimeError("foreign key restriction")
            self.result = None

    def fetchone(self):
        result, self.result = self.result, None
        return result

    def close(self):
        pass


class FakeConnection:
    def __init__(self, account_id, has_account_column=True, fail_delete_user=False):
        self.fake_cursor = FakeCursor(account_id, has_account_column, fail_delete_user)
        self.committed = False
        self.commit_count = 0
        self.rolled_back = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True
        self.commit_count += 1

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_console_refuses_web_owned_profile_deletion(monkeypatch, capsys):
    connection = FakeConnection(account_id=42)
    monkeypatch.setattr(main, "create_connection", lambda: connection)
    monkeypatch.setattr("builtins.input", lambda _: "9")

    main.delete_user()

    output = capsys.readouterr().out
    assert "website Settings" in output
    assert not any(query.startswith("DELETE") for query in connection.fake_cursor.statements)
    assert not connection.committed


def test_console_can_delete_legacy_profile_with_fitness_records(monkeypatch, capsys):
    connection = FakeConnection(account_id=None)
    answers = iter(("9", "yes"))
    monkeypatch.setattr(main, "create_connection", lambda: connection)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    main.delete_user()

    assert any(query.startswith("DELETE FROM fitness_records") for query in connection.fake_cursor.statements)
    assert any(query.startswith("DELETE FROM users") for query in connection.fake_cursor.statements)
    assert any("SELECT account_id FROM users" in query and "FOR UPDATE" in query
               for query in connection.fake_cursor.statements)
    assert connection.committed
    assert "deleted successfully" in capsys.readouterr().out


def test_console_retains_support_for_unmigrated_legacy_schema(monkeypatch, capsys):
    connection = FakeConnection(account_id=None, has_account_column=False)
    answers = iter(("9", "yes"))
    monkeypatch.setattr(main, "create_connection", lambda: connection)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    main.delete_user()

    assert connection.committed
    assert any("SELECT user_id FROM users" in query and "FOR UPDATE" in query
               for query in connection.fake_cursor.statements)
    assert "deleted successfully" in capsys.readouterr().out


def test_console_rechecks_ownership_under_lock_before_deleting(monkeypatch, capsys):
    connection = FakeConnection(account_id=None)

    def answer(prompt):
        if prompt.startswith("Are you sure"):
            # Simulate a concurrent account claim after the initial ownership check.
            connection.fake_cursor.account_id = 42
        return "9" if prompt.startswith("Enter user ID") else "yes"

    monkeypatch.setattr(main, "create_connection", lambda: connection)
    monkeypatch.setattr("builtins.input", answer)

    main.delete_user()

    output = capsys.readouterr().out
    assert "now belongs to a FitTrack web account" in output
    assert any("FOR UPDATE" in query for query in connection.fake_cursor.statements)
    assert not any(query.startswith("DELETE") for query in connection.fake_cursor.statements)
    assert connection.rolled_back


def test_console_rolls_back_legacy_delete_when_foreign_key_restricts_it(monkeypatch, capsys):
    connection = FakeConnection(account_id=None, fail_delete_user=True)
    answers = iter(("9", "yes"))
    monkeypatch.setattr(main, "create_connection", lambda: connection)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    main.delete_user()

    assert connection.rolled_back
    assert connection.commit_count == 1  # Only the display-only read transaction was committed.
    assert "related records still exist" in capsys.readouterr().out
