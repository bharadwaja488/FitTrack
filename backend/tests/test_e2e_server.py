from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_server import (
    CONFIRMATION,
    EXPECTED_DATABASE,
    EXPECTED_DB_ACCOUNT,
    EXPECTED_DB_HOST,
    EXPECTED_DB_USER,
    EXPECTED_SERVER_HOSTNAME,
    validate_test_environment,
    verify_database_identity,
)


def valid_environment():
    return {
        "FITTRACK_TEST_DB_NAME": EXPECTED_DATABASE,
        "FITTRACK_TEST_DB_HOST": EXPECTED_DB_HOST,
        "FITTRACK_TEST_DB_USER": EXPECTED_DB_USER,
        "FITTRACK_TEST_DB_CONFIRM": CONFIRMATION,
        "FITTRACK_RUN_DB_TESTS": "1",
        "FITTRACK_TEST_DB_PASSWORD": "test-only-placeholder",
    }


def test_e2e_server_requires_explicit_test_database_environment():
    with pytest.raises(RuntimeError, match="approved disposable test configuration"):
        validate_test_environment({})


def test_e2e_server_uses_only_the_fixed_test_database_credentials():
    config = validate_test_environment(valid_environment())
    assert config["DB_NAME"] == EXPECTED_DATABASE
    assert config["DB_HOST"] == EXPECTED_DB_HOST
    assert config["DB_USER"] == EXPECTED_DB_USER
    assert config["DB_PASSWORD"] == "test-only-placeholder"


@pytest.mark.parametrize("field,value", [
    ("FITTRACK_TEST_DB_NAME", "fittrack"),
    ("FITTRACK_TEST_DB_HOST", "localhost"),
    ("FITTRACK_TEST_DB_USER", "root"),
    ("FITTRACK_RUN_DB_TESTS", "0"),
])
def test_e2e_server_refuses_mismatched_test_configuration(field, value):
    env = valid_environment()
    env[field] = value
    with pytest.raises(RuntimeError, match="approved disposable test configuration"):
        validate_test_environment(env)


class IdentityCursor:
    def __init__(self, identity):
        self.identity = identity
        self.sql = None

    def execute(self, sql):
        self.sql = sql

    def fetchone(self):
        return self.identity


def identity():
    return {
        "db": EXPECTED_DATABASE,
        "hostname": EXPECTED_SERVER_HOSTNAME,
        "port": 3306,
        "account": EXPECTED_DB_ACCOUNT,
    }


def test_e2e_server_accepts_exact_mysql_identity_without_a_connection():
    cursor = IdentityCursor(identity())
    verify_database_identity(cursor, local_hostname=EXPECTED_SERVER_HOSTNAME)
    assert "SELECT DATABASE()" in cursor.sql
    assert "@@hostname" in cursor.sql and "@@port" in cursor.sql
    assert "CURRENT_USER()" in cursor.sql


@pytest.mark.parametrize("field,value", [
    ("db", "fittrack"),
    ("hostname", "other-host"),
    ("port", 3307),
    ("account", "root@localhost"),
])
def test_e2e_server_fails_closed_for_wrong_mysql_identity(field, value):
    actual = identity()
    actual[field] = value
    with pytest.raises(RuntimeError, match="identity did not match"):
        verify_database_identity(IdentityCursor(actual), local_hostname=EXPECTED_SERVER_HOSTNAME)


def test_e2e_server_fails_closed_if_local_machine_is_not_the_verified_host():
    with pytest.raises(RuntimeError, match="identity did not match"):
        verify_database_identity(IdentityCursor(identity()), local_hostname="other-host")
