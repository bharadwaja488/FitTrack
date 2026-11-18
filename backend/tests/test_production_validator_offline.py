import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
VALIDATOR = BACKEND / "validate_production.py"


def _network_guard(tmp_path):
    hook_dir = tmp_path / "network_guard"
    hook_dir.mkdir()
    (hook_dir / "sitecustomize.py").write_text(
        "import socket\n"
        "def forbidden(*args, **kwargs):\n"
        "    raise RuntimeError('network access forbidden in this test')\n"
        "socket.create_connection = forbidden\n"
        "socket.getaddrinfo = forbidden\n"
        "socket.socket.connect = forbidden\n"
        "socket.socket.connect_ex = forbidden\n",
        encoding="utf-8",
    )
    return hook_dir


def _production_env(tmp_path, hook_dir):
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("test-only CA placeholder", encoding="utf-8")

    env = os.environ.copy()
    env.update({
        "FITTRACK_ENV": "production",
        "SECRET_KEY": "test-only-long-random-key-not-a-real-secret",
        "FLASK_DEBUG": "false",
        "COOKIE_SECURE": "true",
        "FRONTEND_URL": "https://fittrack.example.test",
        "FRONTEND_ORIGINS": "https://fittrack.example.test",
        "DB_HOST": "tidb.example.test",
        "DB_USER": "test-only-user",
        "DB_PASSWORD": "test-only-password",
        "DB_NAME": "fittrack_staging",
        "DB_PORT": "4000",
        "DB_SSL_CA": str(ca_file),
        "DB_SSL_VERIFY_CERT": "true",
        "DB_SSL_VERIFY_IDENTITY": "true",
        "DB_CONNECT_TIMEOUT": "5",
        "DB_READ_TIMEOUT": "20",
        "DB_WRITE_TIMEOUT": "20",
        "RATELIMIT_STORAGE_URI": "rediss://default:test-only-token@cache.example.test:6379/0",
        "TRUSTED_PROXY_HOPS": "0",
        "RENDER": "true",
        "PYTHONPATH": str(hook_dir),
    })
    return env


def _run_validator(env):
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


def test_production_validator_does_not_open_network_connections(tmp_path):
    env = _production_env(tmp_path, _network_guard(tmp_path))
    result = _run_validator(env)
    assert result.returncode == 0, result.stderr
    assert "no database or Redis connection was attempted" in result.stdout
    assert "network access forbidden" not in result.stdout + result.stderr
    assert "test-only-password" not in result.stdout + result.stderr


def test_production_validator_reports_missing_redis_variable_without_values(tmp_path):
    env = _production_env(tmp_path, _network_guard(tmp_path))
    env.pop("RATELIMIT_STORAGE_URI", None)

    result = _run_validator(env)

    assert result.returncode == 1
    assert "RATELIMIT_STORAGE_URI" in result.stderr
    assert "missing" in result.stderr
    assert "rediss://" in result.stderr
    assert "test-only-password" not in result.stderr
    assert "test-only-token" not in result.stderr
    assert "cache.example.test" not in result.stderr


def test_production_validator_reports_malformed_redis_url_without_echoing_it(tmp_path):
    env = _production_env(tmp_path, _network_guard(tmp_path))
    sentinel = "do-not-print-token-value"
    malformed_url = f"rediss://default:{sentinel}@cache.example.test:not-a-port/0"
    env["RATELIMIT_STORAGE_URI"] = malformed_url

    result = _run_validator(env)

    assert result.returncode == 1
    assert "RATELIMIT_STORAGE_URI" in result.stderr
    assert "valid port" in result.stderr
    assert sentinel not in result.stderr
    assert malformed_url not in result.stderr
    assert "cache.example.test" not in result.stderr
    assert "network access forbidden" not in result.stdout + result.stderr


def test_production_validator_reports_malformed_numeric_variable_without_value(tmp_path):
    env = _production_env(tmp_path, _network_guard(tmp_path))
    sentinel = "not-a-real-port-value"
    env["DB_PORT"] = sentinel

    result = _run_validator(env)

    assert result.returncode == 1
    assert "DB_PORT" in result.stderr
    assert "must be an integer" in result.stderr
    assert sentinel not in result.stderr
    assert "test-only-password" not in result.stderr
    assert "network access forbidden" not in result.stdout + result.stderr
