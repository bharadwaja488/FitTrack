"""Explicit, staging-only entry point for migrations 0000 through 0006."""
import argparse
import re
import sys

from staging_target import validate_staging_target


class StagingMigrationFailure(RuntimeError):
    """Safe operator-facing failure that chains the original exception privately."""

    def __init__(self, failed_step=None):
        self.failed_step = failed_step
        super().__init__("Staging migration did not complete.")


def _safe_failed_step(error):
    """Extract only a migration filename and numeric step from runner diagnostics."""
    message = str(error)
    patterns = (
        r"Migration ([A-Za-z0-9_-]+\.sql) failed at schema step (\d+)/(\d+)",
        r"Migration ([A-Za-z0-9_-]+\.sql) step (\d+)/(\d+)",
        r"Migration ([A-Za-z0-9_-]+\.sql).*?step (\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return f"{match.group(1)}, schema step {match.group(2)}"
    return None


def _run_migrations(runner):
    try:
        runner()
    except Exception as error:
        # Keep the original exception chained for callers/debuggers, while the
        # CLI prints only this sanitized report and never connector details.
        raise StagingMigrationFailure(_safe_failed_step(error)) from error


def _report_migration_failure(error):
    print(
        "Staging migration failed. STOP: earlier MySQL DDL statements may already have committed; "
        "the migration version may not have been recorded.",
        file=sys.stderr,
    )
    if error.failed_step:
        print(f"Failed step: {error.failed_step}.", file=sys.stderr)
    else:
        print("Failed migration step could not be identified from safe metadata.", file=sys.stderr)
    print(
        "Next safe action: stop, inspect schema_migrations and the actual schema state, "
        "then determine a reviewed recovery plan before any retry. No migration was retried.",
        file=sys.stderr,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply FitTrack migrations to fittrack_staging only.")
    parser.add_argument("--confirm-staging", action="store_true",
                        help="confirm the verified target is the disposable fittrack_staging database")
    args = parser.parse_args(argv)
    try:
        validate_staging_target()
    except (ValueError, OSError) as error:
        print(f"Staging migration stopped safely: {error}", file=sys.stderr)
        return 2
    if not args.confirm_staging:
        print("Staging migration requires --confirm-staging after target review.", file=sys.stderr)
        return 2

    # Import only after strict target checks. FITTRACK_ENV=production ensures
    # backend/migrate.py will not load the root .env file.
    import migrate
    try:
        _run_migrations(migrate.run)
    except StagingMigrationFailure as error:
        _report_migration_failure(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
