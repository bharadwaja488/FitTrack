from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import migrate

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
BASELINE = MIGRATIONS / migrate.BASELINE_VERSION


def test_production_migration_connect_requires_explicit_expected_target(monkeypatch):
    monkeypatch.setenv("FITTRACK_ENV", "production")
    monkeypatch.setenv("DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_USER", "cluster.fittrack")
    monkeypatch.setenv("DB_PASSWORD", "test-value")
    monkeypatch.setenv("DB_NAME", "fittrack_prod")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_NAME", "fittrack_prod")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_HOST", "other.example.com")
    monkeypatch.setenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt")
    monkeypatch.setenv("DB_SSL_VERIFY_CERT", "true")
    monkeypatch.setenv("DB_SSL_VERIFY_IDENTITY", "true")
    with pytest.raises(migrate.MigrationError, match="DB_HOST does not match"):
        migrate.connect()


def test_migration_never_connects_to_protected_production_database(monkeypatch):
    monkeypatch.setenv("FITTRACK_ENV", "production")
    monkeypatch.setenv("DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_USER", "cluster.fittrack")
    monkeypatch.setenv("DB_PASSWORD", "test-value")
    monkeypatch.setenv("DB_NAME", "fittrack")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_NAME", "fittrack")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt")
    monkeypatch.setenv("DB_SSL_VERIFY_CERT", "true")
    monkeypatch.setenv("DB_SSL_VERIFY_IDENTITY", "true")
    with pytest.raises(migrate.MigrationError, match="protected production database"):
        migrate.connect()


def test_render_migration_defaults_to_production_without_fittrack_environment(monkeypatch):
    monkeypatch.delenv("FITTRACK_ENV", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_NAME", "fittrack_stage")
    with pytest.raises(migrate.MigrationError, match="Production migration requires explicit"):
        migrate.connect()


def test_production_migration_connection_uses_verified_tls_and_ti_db_port(monkeypatch):
    monkeypatch.setenv("FITTRACK_ENV", "production")
    monkeypatch.setenv("DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_USER", "cluster.fittrack")
    monkeypatch.setenv("DB_PASSWORD", "test-value")
    monkeypatch.setenv("DB_NAME", "fittrack_stage")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_NAME", "fittrack_stage")
    monkeypatch.setenv("FITTRACK_EXPECTED_DB_HOST", "tidb.example.com")
    monkeypatch.setenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt")
    monkeypatch.setenv("DB_SSL_VERIFY_CERT", "true")
    monkeypatch.setenv("DB_SSL_VERIFY_IDENTITY", "true")
    monkeypatch.setenv("DB_PORT", "4000")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "5")
    monkeypatch.setenv("DB_READ_TIMEOUT", "20")
    monkeypatch.setenv("DB_WRITE_TIMEOUT", "20")
    captured = {}
    monkeypatch.setattr(migrate.mysql.connector, "connect", lambda **kwargs: captured.update(kwargs) or object())

    migrate.connect()

    assert captured["port"] == 4000
    assert captured["ssl_ca"] == "/etc/ssl/certs/ca-certificates.crt"
    assert captured["ssl_verify_cert"] is True
    assert captured["ssl_verify_identity"] is True


class FakeDatabase:
    def __init__(self):
        self.objects = {}
        self.versions = set()
        self.ddl = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on = None
        self.auto_increment = {}

    def cursor(self, dictionary=False):
        assert dictionary
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class FakeCursor:
    def __init__(self, database):
        self.db = database
        self.rows = []

    def execute(self, sql, params=None):
        sql = sql.strip()
        params = params or ()
        self.rows = []
        if self.db.fail_on and self.db.fail_on in sql:
            raise RuntimeError("simulated DDL failure")
        if sql.startswith("CREATE TABLE IF NOT EXISTS schema_migrations"):
            parsed = migrate.parse_action(sql)
            table_key = ("table", "schema_migrations", "schema_migrations")
            if table_key not in self.db.objects:
                for spec in parsed.objects:
                    self.db.objects[(spec.kind, spec.table.lower(), spec.name.lower())] = spec
            return
        if sql == "SELECT version FROM schema_migrations":
            self.rows = [{"version": version} for version in sorted(self.db.versions)]
            return
        if "information_schema.TABLES" in sql:
            if "TABLE_NAME=%s" in sql:
                table = params[0].lower()
                table_spec = self.db.objects.get(("table", table, table))
                if not table_spec:
                    self.rows = []
                elif "TABLE_COLLATION" in sql:
                    engine, charset, collation = table_spec.definition or (None, None, None)
                    self.rows = [{
                        "TABLE_NAME": table,
                        "ENGINE": engine or "InnoDB",
                        "TABLE_COLLATION": collation or "utf8mb4_0900_ai_ci",
                        "CHARACTER_SET_NAME": charset or "utf8mb4",
                    }]
                else:
                    self.rows = [{"TABLE_NAME": table}]
            else:
                self.rows = [{"TABLE_NAME": table} for kind, table, _ in self.db.objects if kind == "table"]
            return
        if "information_schema.COLUMNS" in sql:
            table, name = (value.lower() for value in params)
            spec = self.db.objects.get(("column", table, name))
            self.rows = ([{"COLUMN_NAME": name, "COLUMN_TYPE": spec.definition[0],
                           "IS_NULLABLE": "YES" if spec.definition[1] else "NO",
                           "COLUMN_DEFAULT": (
                               None if spec.definition[2] == migrate.NO_DEFAULT else spec.definition[2]
                           ),
                           "EXTRA": " ".join(filter(None, (
                               "auto_increment" if spec.definition[3] else "",
                               f"on update {spec.definition[4]}" if spec.definition[4] else "",
                           )))}] if spec else [])
            return
        if "information_schema.STATISTICS" in sql:
            table, name = (value.lower() for value in params)
            spec = self.db.objects.get(("index", table, name))
            self.rows = ([{"INDEX_NAME": name, "NON_UNIQUE": int(spec.definition[0]),
                           "SEQ_IN_INDEX": i + 1, "COLUMN_NAME": column}
                          for i, column in enumerate(spec.definition[1])] if spec else [])
            return
        if "information_schema.KEY_COLUMN_USAGE" in sql:
            table, name = (value.lower() for value in params)
            spec = self.db.objects.get(("foreign_key", table, name))
            self.rows = ([{"COLUMN_NAME": column, "REFERENCED_TABLE_NAME": spec.definition[1],
                           "REFERENCED_COLUMN_NAME": spec.definition[2][i],
                           "DELETE_RULE": spec.definition[3]}
                          for i, column in enumerate(spec.definition[0])] if spec else [])
            return
        if "information_schema.CHECK_CONSTRAINTS" in sql:
            table, name = (value.lower() for value in params)
            spec = self.db.objects.get(("check", table, name))
            self.rows = [{"CHECK_CLAUSE": spec.definition[0]}] if spec else []
            return
        if sql.startswith("INSERT INTO schema_migrations"):
            self.db.versions.add(params[0])
            return
        if sql.upper().startswith("CREATE TABLE"):
            parsed = migrate.parse_action(sql)
            table_spec = next(spec for spec in parsed.objects if spec.kind == "table")
            key = ("table", table_spec.table.lower(), table_spec.table.lower())
            if key in self.db.objects:
                return  # CREATE TABLE IF NOT EXISTS leaves an existing table untouched.
            self.db.ddl.append(sql)
            for spec in parsed.objects:
                self.db.objects[(spec.kind, spec.table.lower(), spec.name.lower())] = spec
            return
        self.db.ddl.append(sql)
        parsed = migrate.parse_action(sql)
        actions = parsed if isinstance(parsed, tuple) else (parsed,)
        for action in actions:
            for spec in action.objects:
                self.db.objects[(spec.kind, spec.table.lower(), spec.name.lower())] = spec

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class MysqlMetadataCursor:
    """Return MySQL information_schema values for the metadata version column."""
    def __init__(self):
        self.rows = []

    def execute(self, sql, params=None):
        params = params or ()
        if "information_schema.TABLES" in sql:
            self.rows = [{"TABLE_NAME": params[0]}]
        elif "information_schema.COLUMNS" in sql:
            self.rows = [{
                "COLUMN_NAME": "version",
                "COLUMN_TYPE": "varchar(100)",
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "EXTRA": "",
            }]
        else:
            raise AssertionError(f"Unexpected metadata verification query: {sql}")

    def fetchall(self):
        return list(self.rows)


def migration_dir(tmp_path, sql):
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "0001_test.sql").write_text(sql, encoding="utf-8")
    return directory


def baseline_dir(tmp_path, include_later=False):
    directory = tmp_path / "baseline_migrations"
    directory.mkdir()
    (directory / BASELINE.name).write_text(BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
    if include_later:
        (directory / "0001_noop.sql").write_text("CREATE TABLE IF NOT EXISTS noop (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB;", encoding="utf-8")
    return directory


def seed_baseline_objects(database):
    for action in migrate._migration_actions(BASELINE):
        for spec in action.objects:
            database.objects[(spec.kind, spec.table.lower(), spec.name.lower())] = spec


SAMPLE = """
CREATE TABLE widgets (
 id INT NOT NULL,
 owner_id INT NOT NULL,
 PRIMARY KEY (id),
 UNIQUE KEY uq_widgets_owner (owner_id),
 CONSTRAINT fk_widgets_owner FOREIGN KEY (owner_id) REFERENCES accounts (account_id) ON DELETE RESTRICT,
 CONSTRAINT chk_widgets_owner CHECK (owner_id > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
ALTER TABLE widgets ADD COLUMN label VARCHAR(20) NULL, ADD KEY ix_widgets_label (label);
CREATE INDEX ix_widgets_id ON widgets (id);
"""


def test_fresh_database_migration_verifies_table_columns_keys_and_foreign_key(tmp_path):
    db = FakeDatabase()
    assert migrate.run(db, migration_dir(tmp_path, SAMPLE)) is True
    assert "0001_test.sql" in db.versions
    assert ("foreign_key", "widgets", "fk_widgets_owner") in db.objects
    assert db.objects[("foreign_key", "widgets", "fk_widgets_owner")].definition[-1] == "RESTRICT"
    assert ("column", "widgets", "label") in db.objects


def test_check_expression_normalization_ignores_redundant_balanced_parentheses():
    expected = "(account_id IS NULL AND activity_level IS NULL) OR " \
               "(account_id IS NOT NULL AND activity_level IS NOT NULL)"
    actual = "((((`account_id` IS NULL) AND ((`activity_level` IS NULL))) OR " \
             "(((`account_id` IS NOT NULL)) AND (`activity_level` IS NOT NULL))))"

    assert migrate._normalize_expression(actual) == migrate._normalize_expression(expected)


def test_check_expression_normalization_ignores_whitespace_backticks_and_case():
    expected = "(`account_id` IS NULL AND `activity_level` IS NULL)"
    actual = " ( ACCOUNT_ID   is   null   AND activity_level IS NULL ) "

    assert migrate._normalize_expression(actual) == migrate._normalize_expression(expected)


def test_check_expression_normalization_ignores_mysql_charset_introducers():
    expected = "goal_type IN ('weight_loss','maintenance','weight_gain','muscle_building')"
    actual = "goal_type in (_utf8mb4'weight_loss', _utf8mb4'maintenance', " \
             "_utf8mb4'weight_gain', _utf8mb4'muscle_building')"

    assert migrate._normalize_expression(actual) == migrate._normalize_expression(expected)


def test_check_expression_normalization_matches_exact_mysql_escaped_metadata_failure():
    expected = "goal_typein('weight_loss','maintenance','weight_gain','muscle_building')"
    actual = r"(`goal_type` in (_utf8mb4\'weight_loss\',_utf8mb4\'maintenance\'," \
             r"_utf8mb4\'weight_gain\',_utf8mb4\'muscle_building\'))"
    spec = migrate.ObjectSpec(
        "check", "fitness_goals", "chk_fitness_goals_type", (expected,),
    )

    normalized_actual = migrate._normalize_expression(actual)
    assert normalized_actual == expected
    assert migrate._require_match(spec, (normalized_actual,), {"CHECK_CLAUSE": actual}) is True


def test_check_expression_normalization_accepts_ordinary_literals_on_both_sides():
    left = "goal_type IN ('weight_loss', 'maintenance', 'weight_gain', 'muscle_building')"
    right = "(goal_type in ('weight_loss','maintenance','weight_gain','muscle_building'))"

    assert migrate._normalize_expression(left) == migrate._normalize_expression(right)


def test_check_expression_normalization_handles_escaped_quote_spellings():
    expected = "label = 'athlete''s plan'"
    actual = r"label = _utf8mb4'athlete\'s plan'"

    assert migrate._normalize_expression(actual) == migrate._normalize_expression(expected)


def test_check_expression_different_literal_values_fail_closed():
    expected = migrate.ObjectSpec(
        "check", "fitness_goals", "chk_fitness_goals_type",
        (migrate._normalize_expression("goal_type IN ('weight_loss','maintenance')"),),
    )
    actual = (migrate._normalize_expression("goal_type IN ('weight_gain','maintenance')"),)

    with pytest.raises(migrate.MigrationError, match="Schema conflict for check"):
        migrate._require_match(expected, actual, {"CHECK_CLAUSE": "different literal"})


@pytest.mark.parametrize(("actual",), [
    ("(account_id IS NULL OR activity_level IS NULL) OR "
     "(account_id IS NOT NULL AND activity_level IS NOT NULL)",),
    ("(account_id IS NULL) OR (account_id IS NOT NULL AND activity_level IS NOT NULL)",),
    ("(other_id IS NULL AND activity_level IS NULL) OR "
     "(account_id IS NOT NULL AND activity_level IS NOT NULL)",),
])
def test_check_expression_normalization_rejects_logical_or_column_changes(actual):
    expected = "(account_id IS NULL AND activity_level IS NULL) OR " \
               "(account_id IS NOT NULL AND activity_level IS NOT NULL)"

    assert migrate._normalize_expression(actual) != migrate._normalize_expression(expected)


def test_check_expression_normalization_matches_exact_parenthesized_between_metadata():
    expected = "calorie_adjustmentisnullorcalorie_adjustmentbetween0and500"
    actual = "((`calorie_adjustment` is null) or " \
             "(`calorie_adjustment` between 0 and 500))"
    spec = migrate.ObjectSpec(
        "check", "fitness_goals", "chk_fitness_goals_adjustment", (expected,),
    )
    normalized_actual = migrate._normalize_expression(actual)

    assert normalized_actual == expected
    assert migrate._require_match(
        spec, (normalized_actual,), {"CHECK_CLAUSE": actual},
    ) is True


@pytest.mark.parametrize(("actual",), [
    ("((calorie_adjustment IS NULL) OR "
     "(calorie_adjustment BETWEEN 0 AND 501))",),
    ("((other_adjustment IS NULL) OR "
     "(other_adjustment BETWEEN 0 AND 500))",),
    ("((calorie_adjustment IS NULL) AND "
     "(calorie_adjustment BETWEEN 0 AND 500))",),
])
def test_check_expression_normalization_keeps_between_bounds_columns_and_operators(actual):
    expected = "calorie_adjustment IS NULL OR calorie_adjustment BETWEEN 0 AND 500"

    assert migrate._normalize_expression(actual) != migrate._normalize_expression(expected)


def test_check_expression_normalization_matches_exact_parenthesized_comparison_metadata():
    expected = "daily_calorie_targetisnullordaily_calorie_target>0"
    actual = "((`daily_calorie_target` is null) or (`daily_calorie_target` > 0))"
    spec = migrate.ObjectSpec(
        "check", "fitness_goals", "chk_fitness_goals_target_calories", (expected,),
    )
    normalized_actual = migrate._normalize_expression(actual)

    assert normalized_actual == expected
    assert migrate._require_match(
        spec, (normalized_actual,), {"CHECK_CLAUSE": actual},
    ) is True


@pytest.mark.parametrize(("actual",), [
    ("((daily_calorie_target IS NULL) OR (daily_calorie_target > 1))",),
    ("((other_calorie_target IS NULL) OR (other_calorie_target > 0))",),
    ("((daily_calorie_target IS NULL) AND (daily_calorie_target > 0))",),
    ("((daily_calorie_target IS NULL) OR (daily_calorie_target >= 0))",),
])
def test_check_expression_verification_rejects_comparison_changes(actual):
    expected = migrate.ObjectSpec(
        "check", "fitness_goals", "chk_fitness_goals_target_calories",
        (migrate._normalize_expression(
            "daily_calorie_target IS NULL OR daily_calorie_target > 0"
        ),),
    )
    actual_expression = (migrate._normalize_expression(actual),)

    with pytest.raises(migrate.MigrationError, match="Schema conflict for check"):
        migrate._require_match(expected, actual_expression, {"CHECK_CLAUSE": actual})


def test_full_existing_migration_chain_runs_and_verifies_against_mock_schema():
    db = FakeDatabase()
    seed_baseline_objects(db)

    migrate.run(db, MIGRATIONS)
    ddl_count = len(db.ddl)
    migrate.run(db, MIGRATIONS)

    assert len(db.versions) == 7
    assert len(db.ddl) == ddl_count


def test_fresh_baseline_creates_only_legacy_tables_and_records_after_verification(tmp_path):
    db = FakeDatabase()

    assert migrate.run(db, baseline_dir(tmp_path)) is True

    assert db.versions == {migrate.BASELINE_VERSION}
    assert {table for kind, table, _ in db.objects if kind == "table"} == {
        "schema_migrations", "users", "fitness_records",
    }
    user_columns = {name for kind, table, name in db.objects if kind == "column" and table == "users"}
    assert user_columns == {
        "user_id", "name", "age", "gender", "height", "weight", "bmi", "daily_calories",
        "goal", "target_calories",
    }
    fitness_columns = {name for kind, table, name in db.objects if kind == "column" and table == "fitness_records"}
    assert fitness_columns == {
        "record_id", "user_id", "record_date", "steps", "distance", "workout_minutes", "calories_burned",
    }
    assert ("foreign_key", "fitness_records", "fitness_records_ibfk_1") in db.objects
    assert ("column", "users", "account_id") not in db.objects
    assert ("column", "users", "daily_step_goal") not in db.objects
    assert ("column", "fitness_records", "record_type") not in db.objects
    assert len(db.ddl) == 2


def test_existing_installation_adopts_baseline_without_ddl_or_autoincrement_change(tmp_path):
    db = FakeDatabase()
    seed_baseline_objects(db)
    db.auto_increment.update(users=74, fitness_records=43)

    migrate.run(db, baseline_dir(tmp_path))

    assert db.ddl == []
    assert db.auto_increment == {"users": 74, "fitness_records": 43}
    assert migrate.BASELINE_VERSION in db.versions


def test_existing_later_migration_history_adopts_matching_baseline(tmp_path):
    db = FakeDatabase()
    seed_baseline_objects(db)
    db.versions.add("0001_accounts_and_personal_profiles.sql")

    migrate.run(db, baseline_dir(tmp_path))

    assert db.ddl == []
    assert migrate.BASELINE_VERSION in db.versions


def test_later_history_with_missing_baseline_tables_fails_before_ddl(tmp_path):
    db = FakeDatabase()
    db.versions.add("0001_accounts_and_personal_profiles.sql")

    with pytest.raises(migrate.MigrationError, match="base table is missing while later migration"):
        migrate.run(db, baseline_dir(tmp_path))

    assert db.ddl == []
    assert migrate.BASELINE_VERSION not in db.versions


def test_ambiguous_baseline_requires_explicit_confirmation_and_resumes_missing_table(tmp_path):
    db = FakeDatabase()
    directory = baseline_dir(tmp_path)
    db.fail_on = "CREATE TABLE IF NOT EXISTS fitness_records"
    with pytest.raises(migrate.MigrationError, match="failed at schema step"):
        migrate.run(db, directory)
    assert ("table", "users", "users") in db.objects
    assert migrate.BASELINE_VERSION not in db.versions

    db.fail_on = None
    with pytest.raises(migrate.MigrationError, match="Ambiguous legacy baseline state"):
        migrate.run(db, directory)
    assert migrate.BASELINE_VERSION not in db.versions

    before_retry = len(db.ddl)
    migrate.run(db, directory, confirm_baseline_recovery=True)
    assert len(db.ddl) == before_retry + 1
    assert migrate.BASELINE_VERSION in db.versions


@pytest.mark.parametrize("conflict", ["column", "primary_key", "foreign_key", "foreign_key_action"])
def test_baseline_conflicts_fail_closed_without_ddl_or_version(tmp_path, conflict):
    db = FakeDatabase()
    seed_baseline_objects(db)
    if conflict == "column":
        db.objects[("column", "users", "name")] = migrate.ObjectSpec(
            "column", "users", "name", ("varchar(80)", False, None, False, None),
        )
    elif conflict == "primary_key":
        db.objects[("index", "users", "primary")] = migrate.ObjectSpec(
            "index", "users", "PRIMARY", (False, ("name",)),
        )
    else:
        key = ("foreign_key", "fitness_records", "fitness_records_ibfk_1")
        definition = db.objects[key].definition
        if conflict == "foreign_key":
            definition = (("user_id",), "accounts", ("account_id",), "RESTRICT")
        else:
            definition = (*definition[:3], "CASCADE")
        db.objects[key] = migrate.ObjectSpec("foreign_key", "fitness_records", "fitness_records_ibfk_1", definition)

    with pytest.raises(migrate.MigrationError, match="Schema conflict"):
        migrate.run(db, baseline_dir(tmp_path))

    assert db.ddl == []
    assert migrate.BASELINE_VERSION not in db.versions


@pytest.mark.parametrize("option,value", [
    ("engine", "MyISAM"),
    ("charset", "latin1"),
    ("collation", "utf8mb4_general_ci"),
])
def test_baseline_table_option_conflicts_fail_closed(tmp_path, option, value):
    db = FakeDatabase()
    seed_baseline_objects(db)
    key = ("table", "users", "users")
    definition = list(db.objects[key].definition)
    definition[{"engine": 0, "charset": 1, "collation": 2}[option]] = value
    db.objects[key] = migrate.ObjectSpec("table", "users", "users", tuple(definition))

    with pytest.raises(migrate.MigrationError, match="Schema conflict for table users.users"):
        migrate.run(db, baseline_dir(tmp_path))

    assert db.ddl == []
    assert migrate.BASELINE_VERSION not in db.versions


def test_baseline_is_idempotent_on_repeated_execution(tmp_path):
    db = FakeDatabase()
    directory = baseline_dir(tmp_path)
    migrate.run(db, directory)
    ddl_count = len(db.ddl)

    migrate.run(db, directory)

    assert len(db.ddl) == ddl_count
    assert db.versions == {migrate.BASELINE_VERSION}


def test_schema_migrations_version_specification_is_non_nullable(tmp_path):
    db = FakeDatabase()
    directory = tmp_path / "empty_migrations"
    directory.mkdir()

    migrate.run(db, directory)

    version = db.objects[("column", "schema_migrations", "version")]
    assert version.definition == ("varchar(100)", False, migrate.NO_DEFAULT, False, None)


def test_mysql_non_nullable_metadata_version_column_verifies(tmp_path):
    db = FakeDatabase()
    directory = tmp_path / "empty_migrations"
    directory.mkdir()
    migrate.run(db, directory)
    version = db.objects[("column", "schema_migrations", "version")]

    assert migrate._object_state(MysqlMetadataCursor(), version) is True


def test_incompatible_metadata_schema_fails_closed_without_ddl_or_version(tmp_path):
    db = FakeDatabase()
    table = migrate.ObjectSpec("table", "schema_migrations", "schema_migrations", ())
    version = migrate.ObjectSpec("column", "schema_migrations", "version", ("varchar(80)", False, None, False, None))
    db.objects[("table", "schema_migrations", "schema_migrations")] = table
    db.objects[("column", "schema_migrations", "version")] = version
    directory = tmp_path / "empty_migrations"
    directory.mkdir()

    with pytest.raises(migrate.MigrationError, match="Schema conflict for column schema_migrations.version"):
        migrate.run(db, directory)

    assert db.ddl == []
    assert db.versions == set()


@pytest.mark.parametrize(("name", "definition", "expected_default", "metadata_default"), [
    ("amount", "amount FLOAT DEFAULT NULL", None, None),
    ("amount", "amount FLOAT", migrate.NO_DEFAULT, None),
    ("amount", "amount INT NOT NULL DEFAULT 0", "0", "0"),
    ("goal", "goal VARCHAR(20) NOT NULL DEFAULT 'maintenance'", "maintenance", "maintenance"),
    ("created_at", "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "current_timestamp", "current_timestamp"),
])
def test_column_default_parsing_and_mysql_metadata_compatibility(
    name, definition, expected_default, metadata_default,
):
    spec = migrate._column_spec("sample", name, definition)
    assert spec.definition[2] == expected_default

    db = FakeDatabase()
    table = migrate.ObjectSpec("table", "sample", "sample", ())
    db.objects[("table", "sample", "sample")] = table
    db.objects[("column", "sample", spec.name)] = spec
    cursor = FakeCursor(db)
    # A MySQL metadata result with NULL is inherently ambiguous between the
    # two nullable default forms; non-NULL defaults remain exact comparisons.
    if metadata_default is not None:
        db.objects[("column", "sample", spec.name)] = migrate.ObjectSpec(
            "column", "sample", spec.name,
            (*spec.definition[:2], metadata_default, *spec.definition[3:]),
        )
    assert migrate._object_state(cursor, spec) is True


def test_incompatible_non_null_column_default_still_fails_closed():
    expected = migrate._column_spec("sample", "amount", "amount INT NOT NULL DEFAULT 0")
    incompatible = ("int", False, "1", False, None)

    with pytest.raises(migrate.MigrationError, match="Schema conflict for column sample.amount"):
        migrate._require_match(expected, incompatible, {"COLUMN_DEFAULT": "1"})


def test_legacy_null_default_spec_matches_mysql_null_metadata():
    # Protect against specs produced by a parser path that still represents
    # DEFAULT NULL as the string seen in the original failure report.
    expected = migrate.ObjectSpec(
        "column", "users", "bmi", ("float", True, "null", False, None),
    )
    actual = ("float", True, None, False, None)

    assert migrate._require_match(expected, actual, {"COLUMN_DEFAULT": None}) is True


def test_explicit_null_default_rejects_a_non_null_metadata_default():
    expected = migrate._column_spec("sample", "amount", "amount FLOAT DEFAULT NULL")
    incompatible = ("float", True, "0", False, None)

    with pytest.raises(migrate.MigrationError, match="Schema conflict for column sample.amount"):
        migrate._require_match(expected, incompatible, {"COLUMN_DEFAULT": "0"})


@pytest.mark.parametrize(("definition", "actual_default", "matches"), [
    ("protein_g DECIMAL(9,2) NOT NULL DEFAULT 0", "0.00", True),
    ("protein_g DECIMAL(9,2) NOT NULL DEFAULT 0.0", "0.00", True),
    ("protein_g DECIMAL(9,2) NOT NULL DEFAULT 0", "0.01", False),
    ("session_version INT NOT NULL DEFAULT 0", "0.0", True),
    ("label VARCHAR(20) NOT NULL DEFAULT '0.00'", "0", False),
    ("created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP", "current_timestamp", True),
])
def test_column_default_verification_is_type_aware(definition, actual_default, matches):
    name = definition.split()[0]
    expected = migrate._column_spec("sample", name, definition)
    actual = (
        expected.definition[0], expected.definition[1], actual_default,
        expected.definition[3], expected.definition[4],
    )

    if matches:
        assert migrate._require_match(expected, actual, {"COLUMN_DEFAULT": actual_default}) is True
    else:
        with pytest.raises(migrate.MigrationError, match="Schema conflict for column sample"):
            migrate._require_match(expected, actual, {"COLUMN_DEFAULT": actual_default})


def test_repeated_migration_execution_verifies_and_does_not_repeat_ddl(tmp_path):
    db = FakeDatabase()
    directory = migration_dir(tmp_path, SAMPLE)
    migrate.run(db, directory)
    original_ddl_count = len(db.ddl)
    migrate.run(db, directory)
    assert len(db.ddl) == original_ddl_count
    assert list(db.versions) == ["0001_test.sql"]


def test_partially_applied_migration_resumes_only_missing_objects(tmp_path):
    db = FakeDatabase()
    db.fail_on = "CREATE INDEX ix_widgets_id"
    directory = migration_dir(tmp_path, SAMPLE)
    with pytest.raises(migrate.MigrationError, match="No migration version was recorded"):
        migrate.run(db, directory)
    assert not db.versions
    before_resume = len(db.ddl)
    db.fail_on = None
    migrate.run(db, directory)
    assert "0001_test.sql" in db.versions
    assert len(db.ddl) == before_resume + 1


def test_partially_present_alter_executes_only_missing_clause(tmp_path):
    db = FakeDatabase()
    db.objects[("table", "users", "users")] = migrate.ObjectSpec("table", "users", "users", ())
    first = migrate.ObjectSpec("column", "users", "first", ("int", True, None, False, None))
    db.objects[("column", "users", "first")] = first
    directory = migration_dir(tmp_path, "ALTER TABLE users ADD COLUMN first INT NULL, ADD COLUMN second VARCHAR(10) NULL;")

    migrate.run(db, directory)

    assert db.ddl == ["ALTER TABLE `users` ADD COLUMN second VARCHAR(10) NULL"]


def test_duplicate_version_is_not_recorded_twice(tmp_path):
    db = FakeDatabase()
    db.versions.add("0001_test.sql")
    directory = migration_dir(tmp_path, SAMPLE)
    with pytest.raises(migrate.MigrationError, match="recorded as applied.*missing"):
        migrate.run(db, directory)


def test_missing_object_in_recorded_migration_is_reported_as_schema_drift(tmp_path):
    db = FakeDatabase()
    db.versions.add("0001_test.sql")
    db.objects[("table", "widgets", "widgets")] = migrate.ObjectSpec("table", "widgets", "widgets", ())
    directory = migration_dir(tmp_path, SAMPLE)
    with pytest.raises(migrate.MigrationError, match="missing expected column"):
        migrate.run(db, directory)


def test_conflicting_existing_column_definition_stops_without_ddl(tmp_path):
    db = FakeDatabase()
    db.objects[("table", "widgets", "widgets")] = migrate.ObjectSpec("table", "widgets", "widgets", ())
    db.objects[("column", "widgets", "id")] = migrate.ObjectSpec("column", "widgets", "id", ("bigint", False, None, False, None))
    directory = migration_dir(tmp_path, SAMPLE)
    with pytest.raises(migrate.MigrationError, match="Schema conflict"):
        migrate.run(db, directory)
    assert not db.ddl


def test_conflicting_foreign_key_delete_rule_stops_without_ddl(tmp_path):
    db = FakeDatabase()
    create_action = migrate.parse_action(SAMPLE.split(";", 1)[0])
    for spec in create_action.objects:
        db.objects[(spec.kind, spec.table.lower(), spec.name.lower())] = spec
    wrong_fk = migrate.ObjectSpec(
        "foreign_key", "widgets", "fk_widgets_owner",
        (("owner_id",), "accounts", ("account_id",), "CASCADE"),
    )
    db.objects[("foreign_key", "widgets", "fk_widgets_owner")] = wrong_fk
    directory = migration_dir(tmp_path, SAMPLE)

    with pytest.raises(migrate.MigrationError, match="Schema conflict for foreign_key"):
        migrate.run(db, directory)


@pytest.mark.parametrize(("expected_rule", "actual_rule", "matches"), [
    ("RESTRICT", "NO ACTION", True),
    ("NO ACTION", "RESTRICT", True),
    ("CASCADE", "RESTRICT", False),
    ("SET NULL", "NO ACTION", False),
])
def test_mysql_foreign_key_delete_rule_metadata_comparison(expected_rule, actual_rule, matches):
    db = FakeDatabase()
    table = migrate.ObjectSpec("table", "fitness_records", "fitness_records", ())
    expected = migrate.ObjectSpec(
        "foreign_key", "fitness_records", "fitness_records_ibfk_1",
        (("user_id",), "users", ("user_id",), expected_rule),
    )
    actual = migrate.ObjectSpec(
        "foreign_key", "fitness_records", "fitness_records_ibfk_1",
        (("user_id",), "users", ("user_id",), actual_rule),
    )
    db.objects[("table", "fitness_records", "fitness_records")] = table
    db.objects[("foreign_key", "fitness_records", "fitness_records_ibfk_1")] = actual

    if matches:
        assert migrate._object_state(FakeCursor(db), expected) is True
    else:
        with pytest.raises(migrate.MigrationError, match="Schema conflict for foreign_key"):
            migrate._object_state(FakeCursor(db), expected)
    assert not db.ddl


def test_missing_base_table_stops_before_any_ddl(tmp_path):
    directory = migration_dir(tmp_path, "ALTER TABLE users ADD COLUMN flag INT NULL;")
    db = FakeDatabase()
    with pytest.raises(migrate.MigrationError, match="Required table users is missing"):
        migrate.run(db, directory)
    assert not db.ddl


def test_ddl_failure_reports_step_and_recovery_guidance_without_recording_version(tmp_path):
    db = FakeDatabase()
    db.fail_on = "ALTER TABLE widgets ADD COLUMN label"
    directory = migration_dir(tmp_path, SAMPLE)
    with pytest.raises(migrate.MigrationError, match="failed at schema step.*rerun"):
        migrate.run(db, directory)
    assert not db.versions
    assert db.rollbacks >= 1


@pytest.mark.parametrize("path", sorted(MIGRATIONS.glob("*.sql")), ids=lambda path: path.name)
def test_existing_migration_files_are_fully_supported_and_additive(path):
    actions = migrate._migration_actions(path)
    assert actions, path.name
    content = path.read_text(encoding="utf-8").lower()
    assert "drop table" not in content
    assert "truncate" not in content
