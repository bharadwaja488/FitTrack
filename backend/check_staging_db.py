"""Verify staging TiDB connectivity, selected database, and TLS without changing data."""
import sys

from staging_target import validate_staging_target


def main():
    try:
        validate_staging_target()
    except (ValueError, OSError) as error:
        print(f"Staging database check stopped safely: {error}", file=sys.stderr)
        return 2
    import migrate
    connection = None
    cursor = None
    try:
        connection = migrate.connect()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE(), @@hostname")
        database, _server_hostname = cursor.fetchone()
        if database != "fittrack_staging":
            print("Staging database check failed: server selected an unexpected database.", file=sys.stderr)
            return 1
    except Exception:
        # Connector errors can include host and account details; keep output generic.
        print("Staging database connection or TLS verification failed.", file=sys.stderr)
        return 1
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
    print("Staging database connectivity and selected database verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
