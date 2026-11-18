import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
VALIDATOR = BACKEND / "validate_production.py"


def test_production_validator_does_not_open_network_connections(tmp_path):
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("test-only CA placeholder", encoding="utf-8")
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
        "RATELIMIT_STORAGE_URI": "rediss://cache.example.test/0",
        "TRUSTED_PROXY_HOPS": "0",
        "RENDER": "true",
        "PYTHONPATH": str(hook_dir),
    })
    result = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "no database or Redis connection was attempted" in result.stdout
    assert "network access forbidden" not in result.stdout + result.stderr
    assert "test-only-password" not in result.stdout + result.stderr
