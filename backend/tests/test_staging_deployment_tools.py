import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from staging_target import validate_staging_target
from migrate_staging import (
    StagingMigrationFailure,
    _run_migrations,
    main as migration_main,
)


@pytest.fixture
def staging_env(tmp_path, monkeypatch):
    ca_file = tmp_path / "tidb-ca.pem"
    ca_file.write_text("test CA placeholder", encoding="utf-8")
    settings = {
        "FITTRACK_ENV": "production",
        "DB_NAME": "fittrack_staging",
        "FITTRACK_EXPECTED_DB_NAME": "fittrack_staging",
        "DB_HOST": "staging.example.test",
        "FITTRACK_EXPECTED_DB_HOST": "staging.example.test",
        "DB_PORT": "4000",
        "DB_SSL_VERIFY_CERT": "true",
        "DB_SSL_VERIFY_IDENTITY": "true",
        "DB_SSL_CA": str(ca_file),
        "DB_USER": "staging_user",
        "DB_PASSWORD": "test-only-placeholder",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    return settings


def test_staging_target_requires_exact_disposable_database(staging_env):
    assert validate_staging_target()[0] == "staging.example.test"


@pytest.mark.parametrize("key,value", [
    ("DB_NAME", "fittrack"),
    ("FITTRACK_EXPECTED_DB_NAME", "fittrack"),
    ("FITTRACK_EXPECTED_DB_HOST", "other.example.test"),
    ("DB_PORT", "3306"),
    ("DB_SSL_VERIFY_CERT", "false"),
    ("DB_SSL_VERIFY_IDENTITY", "false"),
    ("FITTRACK_ENV", "development"),
])
def test_staging_target_rejects_unsafe_settings(staging_env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        validate_staging_target()


def test_staging_target_requires_existing_ca_file(staging_env, monkeypatch):
    monkeypatch.setenv("DB_SSL_CA", str(Path(staging_env["DB_SSL_CA"]).with_name("missing.pem")))
    with pytest.raises(ValueError, match="DB_SSL_CA"):
        validate_staging_target()


@pytest.mark.parametrize("key", ["DB_USER", "DB_PASSWORD"])
def test_staging_target_rejects_missing_credentials(staging_env, monkeypatch, key):
    monkeypatch.setenv(key, "")
    with pytest.raises(ValueError, match=key):
        validate_staging_target()


def test_staging_migration_without_confirmation_never_calls_runner(staging_env, monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "migrate", SimpleNamespace(run=lambda: calls.append("run")))
    assert migration_main([]) == 2
    assert calls == []


def test_mysql_connector_receives_certificate_and_hostname_verification(staging_env, monkeypatch):
    import migrate

    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(migrate.mysql.connector, "connect", fake_connect)
    migrate.connect()
    assert calls[0]["ssl_ca"] == staging_env["DB_SSL_CA"]
    assert calls[0]["ssl_verify_cert"] is True
    assert calls[0]["ssl_verify_identity"] is True


def test_migration_failure_chains_original_exception_without_printing_it():
    original = RuntimeError("Migration 0006_advanced_activity_tracking.sql failed at schema step 2/5; password=do-not-print")
    with pytest.raises(StagingMigrationFailure) as raised:
        _run_migrations(lambda: (_ for _ in ()).throw(original))
    assert raised.value.__cause__ is original
    assert raised.value.failed_step == "0006_advanced_activity_tracking.sql, schema step 2"


def test_migration_failure_warns_about_partial_ddl_and_redacts_connector_details(
    staging_env, monkeypatch, capsys,
):
    secret = "mysql://staging-user:never-print-this@db.example.test/fittrack_staging"
    original = RuntimeError(
        "Migration 0006_advanced_activity_tracking.sql failed at schema step 2/5; "
        f"connection={secret}; password=never-print-this"
    )
    calls = []

    def fail_once():
        calls.append("run")
        raise original

    monkeypatch.setattr("migrate_staging.validate_staging_target", lambda: None)
    monkeypatch.setitem(sys.modules, "migrate", SimpleNamespace(run=fail_once))
    assert migration_main(["--confirm-staging"]) == 1
    captured = capsys.readouterr()
    report = captured.out + captured.err
    assert "earlier MySQL DDL statements may already have committed" in report
    assert "migration version may not have been recorded" in report
    assert "0006_advanced_activity_tracking.sql, schema step 2" in report
    assert "stop, inspect schema_migrations and the actual schema state" in report
    assert "reviewed recovery plan before any retry" in report
    assert "never-print-this" not in report
    assert "mysql://" not in report
    assert calls == ["run"]


def test_checklist_has_clean_powershell_commands_for_existing_files():
    root = BACKEND.parent
    checklist = (root / "DEPLOYMENT_CHECKLIST.md").read_text(encoding="utf-8")
    assert not any(ord(character) < 32 and character not in "\n\r\t" for character in checklist)
    assert "$fittrackPython = Join-Path" in checklist
    assert "(Join-Path 'backend' 'validate_production.py')" in checklist
    assert "(Join-Path 'backend' 'check_staging_db.py')" in checklist
    assert "(Join-Path 'backend' 'migrate_staging.py') --confirm-staging" in checklist
    assert "(Join-Path 'scripts' 'smoke_deployment.py') --frontend-url $stagingFrontendUrl" in checklist
    blocks = []
    lines = checklist.splitlines()
    in_powershell = False
    block = []
    for line in lines:
        if line == "```powershell":
            in_powershell = True
            block = []
        elif in_powershell and line == "```":
            blocks.append(block)
            in_powershell = False
        elif in_powershell:
            block.append(line)
    assert len(blocks) == 3
    native_lines = [
        line for block in blocks for line in block
        if line.startswith("& $fittrackPython")
    ]
    assert native_lines
    for block in blocks:
        for index, line in enumerate(block):
            if line.startswith("& $fittrackPython"):
                assert index + 1 < len(block)
                assert block[index + 1].startswith("if ($LASTEXITCODE -ne 0)"), line
    assert "migrate_staging.py" not in "\n".join(blocks[0])
    assert "migrate_staging.py" in "\n".join(blocks[1])
    assert "APPLY FITTRACK STAGING" in "\n".join(blocks[1])
    for relative_path in (
        ".venv/Scripts/python.exe",
        "backend/validate_production.py",
        "backend/check_staging_db.py",
        "backend/migrate_staging.py",
        "scripts/smoke_deployment.py",
    ):
        assert (root / relative_path).exists(), relative_path
