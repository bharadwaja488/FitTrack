import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app import database


def test_connection_passes_ti_db_tls_port_and_timeouts(monkeypatch):
    app = create_app()
    app.config.update({
        "DB_HOST": "tidb.example.com",
        "DB_PORT": 4000,
        "DB_USER": "cluster.fittrack",
        "DB_PASSWORD": "test-placeholder",
        "DB_NAME": "fittrack_stage",
        "DB_SSL_CA": "/etc/ssl/certs/ca-certificates.crt",
        "DB_SSL_VERIFY_CERT": True,
        "DB_SSL_VERIFY_IDENTITY": True,
        "DB_CONNECT_TIMEOUT": 5,
        "DB_READ_TIMEOUT": 20,
        "DB_WRITE_TIMEOUT": 20,
    })
    cursor = Mock()
    connection = Mock()
    connection.cursor.return_value = cursor
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return connection

    monkeypatch.setattr(database.mysql.connector, "connect", connect)
    with app.app_context(), database.connection():
        pass

    assert captured["port"] == 4000
    assert captured["ssl_ca"] == "/etc/ssl/certs/ca-certificates.crt"
    assert captured["ssl_verify_cert"] is True
    assert captured["ssl_verify_identity"] is True
    assert captured["connection_timeout"] == 5
    assert captured["read_timeout"] == 20
    assert captured["write_timeout"] == 20
    cursor.close.assert_called_once()
    connection.close.assert_called_once()
