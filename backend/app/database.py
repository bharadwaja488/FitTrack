from contextlib import contextmanager
import mysql.connector
from flask import current_app


@contextmanager
def connection(dictionary=True):
    cfg = current_app.config
    conn = mysql.connector.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        connection_timeout=cfg["DB_CONNECT_TIMEOUT"],
        read_timeout=cfg["DB_READ_TIMEOUT"],
        write_timeout=cfg["DB_WRITE_TIMEOUT"],
        ssl_ca=cfg["DB_SSL_CA"] or None,
        ssl_verify_cert=cfg["DB_SSL_VERIFY_CERT"],
        ssl_verify_identity=cfg["DB_SSL_VERIFY_IDENTITY"],
    )
    cursor = None
    try:
        cursor = conn.cursor(dictionary=dictionary)
        yield conn, cursor
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
