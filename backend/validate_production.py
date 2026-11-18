"""Run the application's fail-closed production configuration checks offline."""
import os
import sys


def main():
    if os.environ.get("FITTRACK_ENV", "").strip().lower() not in {"prod", "production"}:
        print("Set FITTRACK_ENV=production before validating hosted configuration.", file=sys.stderr)
        return 2
    try:
        from app import create_app
        create_app()
    except Exception:
        # Avoid echoing configuration values or connector details into CI logs.
        print("Production configuration validation failed; verify required secret settings.", file=sys.stderr)
        return 1
    print("Production configuration validated; no database or Redis connection was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
