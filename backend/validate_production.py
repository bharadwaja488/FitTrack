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
    except Exception as error:
        # ProductionConfigurationError contains only fixed, value-free diagnostics.
        issues = getattr(error, "issues", None)
        if (error.__class__.__name__ == "ProductionConfigurationError"
                and isinstance(issues, (tuple, list))
                and all(isinstance(issue, str) for issue in issues)):
            print("Production configuration validation failed:", file=sys.stderr)
            for issue in issues:
                print(f"- {issue}", file=sys.stderr)
            return 1
        # Never print raw exceptions: connector/config parser details can contain credentials.
        print("Production configuration validation failed; verify required secret settings.", file=sys.stderr)
        return 1
    print("Production configuration validated; no database or Redis connection was attempted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
