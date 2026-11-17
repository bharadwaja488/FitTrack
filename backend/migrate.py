"""Recoverable runner for FitTrack's existing additive MySQL migrations.

MySQL DDL is not transactionally rolled back on all supported server versions.
The runner therefore inspects every object before executing DDL and records a
version only after its full expected schema has been verified.
"""
from dataclasses import dataclass
import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys
import os

import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = Path(__file__).resolve().parent / "migrations"
BASELINE_VERSION = "0000_legacy_base_schema.sql"
# MySQL reports COLUMN_DEFAULT as NULL both for an implicit nullable default
# and for an explicit DEFAULT NULL. Keep the parsed SQL states distinct while
# allowing for that information_schema limitation during verification.
NO_DEFAULT = "<no explicit default>"
def resolve_environment():
    explicit_environment = os.getenv("FITTRACK_ENV")
    if explicit_environment:
        return explicit_environment.strip().lower()
    if os.getenv("RENDER", "").strip().lower() == "true":
        return "production"
    return os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()


_environment = resolve_environment()
if _environment not in {"prod", "production"}:
    load_dotenv(ROOT / ".env")
_environment = resolve_environment()


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObjectSpec:
    kind: str
    table: str
    name: str
    definition: tuple


@dataclass(frozen=True)
class MigrationAction:
    sql: str
    objects: tuple
    clauses: tuple = ()


def connect():
    environment = resolve_environment()
    if os.getenv("DB_NAME", "").strip().casefold() == "fittrack":
        raise MigrationError("Refusing to connect to the protected production database 'fittrack'.")
    if environment in {"prod", "production"}:
        required = (
            "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "FITTRACK_EXPECTED_DB_NAME",
            "FITTRACK_EXPECTED_DB_HOST", "DB_SSL_CA",
        )
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise MigrationError(f"Production migration requires explicit environment settings: {', '.join(missing)}.")
        if os.getenv("DB_NAME") != os.getenv("FITTRACK_EXPECTED_DB_NAME"):
            raise MigrationError("Production DB_NAME does not match FITTRACK_EXPECTED_DB_NAME; refusing to connect.")
        if os.getenv("DB_HOST") != os.getenv("FITTRACK_EXPECTED_DB_HOST"):
            raise MigrationError("Production DB_HOST does not match FITTRACK_EXPECTED_DB_HOST; refusing to connect.")
        if (os.getenv("DB_SSL_VERIFY_CERT", "").lower() != "true"
                or os.getenv("DB_SSL_VERIFY_IDENTITY", "").lower() != "true"):
            raise MigrationError("Production migration requires verified database TLS.")
    try:
        port = int(os.getenv("DB_PORT", "4000" if environment in {"prod", "production"} else "3306"))
        connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        read_timeout = int(os.getenv("DB_READ_TIMEOUT", "20"))
        write_timeout = int(os.getenv("DB_WRITE_TIMEOUT", "20"))
    except ValueError:
        raise MigrationError("Database port and timeout settings must be integers.") from None
    if not 1 <= port <= 65535 or min(connect_timeout, read_timeout, write_timeout) <= 0:
        raise MigrationError("Database port and timeout settings are outside their valid ranges.")
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"), port=port, user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"), database=os.getenv("DB_NAME"),
        connection_timeout=connect_timeout, read_timeout=read_timeout, write_timeout=write_timeout,
        ssl_ca=os.getenv("DB_SSL_CA") or None,
        ssl_verify_cert=os.getenv("DB_SSL_VERIFY_CERT", "false").lower() == "true",
        ssl_verify_identity=os.getenv("DB_SSL_VERIFY_IDENTITY", "false").lower() == "true",
    )


def _strip_comments(sql):
    return re.sub(r"(?m)^\s*--.*(?:\n|$)", "", sql)


def _split_top_level(text):
    """Split comma-separated SQL clauses while ignoring nested commas."""
    pieces, start, depth = [], 0, 0
    quote = None
    i = 0
    while i < len(text):
        char = text[i]
        if quote:
            if char == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 1
                else:
                    quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            pieces.append(text[start:i].strip())
            start = i + 1
        i += 1
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if piece]


def _column_spec(table, name, definition):
    match = re.match(r"^\s*`?([\w]+)`?\s+([A-Z]+(?:\s*\([^)]*\))?)(.*)$", definition, re.I | re.S)
    if not match or match.group(1).lower() != name.lower():
        raise MigrationError(f"Cannot safely inspect column definition for {table}.{name}.")
    data_type = re.sub(r"\s+", "", match.group(2)).lower()
    if data_type == "boolean":
        data_type = "tinyint(1)"  # MySQL's BOOLEAN alias.
    elif data_type in {"int", "integer"}:
        data_type = "int"  # Ignore legacy integer display widths such as INT(11).
    remainder = match.group(3).upper()
    nullable = not bool(re.search(r"\bNOT\s+NULL\b", remainder))
    default_match = re.search(
        r"\bDEFAULT\s+(CURRENT_TIMESTAMP(?:\(\))?|TRUE|FALSE|NULL|[+-]?\d+(?:\.\d+)?|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")",
        remainder, re.I,
    )
    default_value = _normalize_default(default_match.group(1)) if default_match else NO_DEFAULT
    auto_increment = bool(re.search(r"\bAUTO_INCREMENT\b", remainder, re.I))
    on_update = re.search(r"\bON\s+UPDATE\s+(CURRENT_TIMESTAMP(?:\(\))?)", remainder, re.I)
    on_update_value = on_update.group(1).lower() if on_update else None
    return ObjectSpec("column", table, name, (data_type, nullable, default_value, auto_increment, on_update_value))


def _normalize_default(value):
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "null":
        return None
    if normalized == "false":
        return "0"
    if normalized == "true":
        return "1"
    if normalized.startswith("'") and normalized.endswith("'"):
        return normalized[1:-1].replace("''", "'")
    if normalized.startswith('"') and normalized.endswith('"'):
        return normalized[1:-1].replace('""', '"')
    return normalized


def _column_defaults_equal(data_type, expected, actual):
    """Compare numeric defaults numerically only for numeric SQL columns."""
    if expected == actual:
        return True
    if expected is None or actual is None or expected == NO_DEFAULT:
        return False
    base_type = re.match(r"[a-z]+", data_type.lower())
    if not base_type or base_type.group(0) not in {
        "tinyint", "smallint", "mediumint", "int", "bigint", "decimal", "numeric",
        "float", "double", "real",
    }:
        return False
    number = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$", re.I)
    if not number.fullmatch(str(expected)) or not number.fullmatch(str(actual)):
        return False
    try:
        return Decimal(str(expected)) == Decimal(str(actual))
    except InvalidOperation:
        return False


def _normalize_delete_rule(value):
    if value is None:
        return None
    normalized = value.strip().upper()
    # InnoDB treats these as the same restrictive action; MySQL may expose
    # either spelling through information_schema for an omitted action.
    return "RESTRICT" if normalized in {"RESTRICT", "NO ACTION"} else normalized


def _clause_spec(table, clause):
    clause = clause.strip().rstrip(";")
    column = re.match(r"ADD\s+COLUMN\s+`?(\w+)`?\s+(.+)$", clause, re.I | re.S)
    if column:
        return _column_spec(table, column.group(1), f"{column.group(1)} {column.group(2)}")
    index = re.match(r"ADD\s+(UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?\s*\(([^)]*)\)", clause, re.I | re.S)
    if index:
        columns = tuple(re.sub(r"`", "", part.strip().split()[0]).lower() for part in index.group(3).split(","))
        return ObjectSpec("index", table, index.group(2), (not bool(index.group(1)), columns))
    foreign = re.match(
        r"ADD\s+CONSTRAINT\s+`?(\w+)`?\s+FOREIGN\s+KEY\s*\(([^)]*)\)\s+REFERENCES\s+`?(\w+)`?\s*\(([^)]*)\)(.*)$",
        clause, re.I | re.S,
    )
    if foreign:
        delete = re.search(r"ON\s+DELETE\s+(RESTRICT|CASCADE|SET\s+NULL|NO\s+ACTION)", foreign.group(5), re.I)
        return ObjectSpec("foreign_key", table, foreign.group(1), (
            tuple(x.strip().strip("`").lower() for x in foreign.group(2).split(",")),
            foreign.group(3).strip("`").lower(),
            tuple(x.strip().strip("`").lower() for x in foreign.group(4).split(",")),
            re.sub(r"\s+", " ", delete.group(1).upper()) if delete else "RESTRICT",
        ))
    check = re.match(r"ADD\s+CONSTRAINT\s+`?(\w+)`?\s+CHECK\s*\((.*)\)$", clause, re.I | re.S)
    if check:
        return ObjectSpec("check", table, check.group(1), (_normalize_expression(check.group(2)),))
    raise MigrationError(f"Unsupported migration clause; refusing to skip it: {clause}")


def _normalize_expression(value):
    # Normalize SQL tokens without changing string-literal values. MySQL may
    # include a character-set introducer before literals in CHECK_CLAUSE.
    lexical = []
    index = 0

    def escaped_quote_closes_literal(position):
        after = position + 2
        while after < len(value) and value[after].isspace():
            after += 1
        return after == len(value) or value[after] in ",);]}>"

    while index < len(value):
        char = value[index]
        escaped_opening_quote = (
            char == "\\" and index + 1 < len(value)
            and value[index + 1] in ("'", '"')
        )
        if char in ("'", '"') or escaped_opening_quote:
            quote = value[index + 1] if escaped_opening_quote else char
            literal = []
            index += 2 if escaped_opening_quote else 1
            while index < len(value):
                char = value[index]
                if char == "\\" and index + 1 < len(value):
                    following = value[index + 1]
                    if following == quote and escaped_quote_closes_literal(index):
                        index += 2
                        break
                    if following in (quote, "\\"):
                        literal.append(following)
                    else:
                        literal.extend((char, following))
                    index += 2
                    continue
                if char == quote:
                    if index + 1 < len(value) and value[index + 1] == quote:
                        literal.append(quote)
                        index += 2
                        continue
                    index += 1
                    break
                literal.append(char)
                index += 1
            lexical.append("'" + "".join(literal).replace("'", "''") + "'")
            continue
        if char == "`":
            index += 1
            continue
        if char == "_":
            introducer = re.match(r"_[A-Za-z0-9]+", value[index:])
            token_boundary = index == 0 or not (
                value[index - 1].isalnum() or value[index - 1] in "_$`"
            )
            if introducer and token_boundary:
                after = index + introducer.end()
                while after < len(value) and value[after].isspace():
                    after += 1
                if (after < len(value) and value[after] in ("'", '"')) or (
                    after + 1 < len(value) and value[after] == "\\"
                    and value[after + 1] in ("'", '"')
                ):
                    index = after
                    continue
        if char.isspace():
            if lexical and lexical[-1] != " ":
                lexical.append(" ")
            index += 1
            continue
        lexical.append(char.lower())
        index += 1
    value = "".join(lexical).strip()

    def outer_pair_encloses_all(expression):
        if not (expression.startswith("(") and expression.endswith(")")):
            return False
        depth = 0
        quote = None
        index = 0
        while index < len(expression):
            char = expression[index]
            if quote:
                if char == quote:
                    if index + 1 < len(expression) and expression[index + 1] == quote:
                        index += 1
                    else:
                        quote = None
            elif char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(expression) - 1:
                    return False
                if depth < 0:
                    return False
            index += 1
        return depth == 0

    def strip_outer(expression):
        while outer_pair_encloses_all(expression):
            expression = expression[1:-1]
        return expression

    def matching_close(expression, start):
        depth = 0
        quote = None
        index = start
        while index < len(expression):
            char = expression[index]
            if quote:
                if char == quote:
                    if index + 1 < len(expression) and expression[index + 1] == quote:
                        index += 1
                    else:
                        quote = None
            elif char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return None

    def top_level_operators(expression):
        """Tokenize boolean/comparison operators outside groups and literals."""
        words, comparisons = [], []
        depth = 0
        index = 0
        while index < len(expression):
            char = expression[index]
            if char in ("'", '"'):
                quote = char
                index += 1
                while index < len(expression):
                    if expression[index] == quote:
                        if index + 1 < len(expression) and expression[index + 1] == quote:
                            index += 2
                            continue
                        index += 1
                        break
                    index += 1
                continue
            if char == "(":
                depth += 1
                index += 1
                continue
            if char == ")":
                depth -= 1
                index += 1
                continue
            if depth == 0 and (char.isalpha() or char in "_$"):
                match = re.match(r"[a-z_$][\w$]*", expression[index:])
                word = match.group(0)
                words.append(word)
                index += len(word)
                continue
            if depth == 0:
                operator = next((op for op in ("<=", ">=", "<>", "!=", "=", "<", ">")
                                  if expression.startswith(op, index)), None)
                if operator:
                    comparisons.append(operator)
                    index += len(operator)
                    continue
            index += 1
        return words, comparisons

    def is_atomic_predicate(expression):
        identifier = r"[a-z_$][\w$]*(?:\.[a-z_$][\w$]*)?"
        if re.fullmatch(rf"{identifier}\s+is\s+(?:not\s+)?null", expression):
            return True
        operand = rf"(?:[+-]?(?:\d+(?:\.\d*)?|\.\d+)|'(?:''|[^'])*'|{identifier})"
        if re.fullmatch(rf"{identifier}\s+between\s+{operand}\s+and\s+{operand}", expression):
            return True
        if re.fullmatch(rf"{identifier}\s+in\s*\(.*\)", expression):
            return True
        words, comparisons = top_level_operators(expression)
        logical = False
        between_and = False
        for word in words:
            if word == "between":
                between_and = True
            elif word == "and" and between_and:
                between_and = False
            elif word in {"and", "or"}:
                logical = True
        return not logical and len(comparisons) == 1

    def normalize_nested_groups(expression):
        pieces = []
        index = 0
        while index < len(expression):
            if expression[index] in ("'", '"'):
                quote = expression[index]
                end = index + 1
                while end < len(expression):
                    if expression[end] == quote:
                        if end + 1 < len(expression) and expression[end + 1] == quote:
                            end += 2
                            continue
                        end += 1
                        break
                    end += 1
                pieces.append(expression[index:end])
                index = end
                continue
            if expression[index] != "(":
                pieces.append(expression[index])
                index += 1
                continue
            closing = matching_close(expression, index)
            if closing is None:
                pieces.append(expression[index:])
                break
            inner = normalize_nested_groups(strip_outer(expression[index + 1:closing]))
            # MySQL may wrap each IS NULL predicate in extra parentheses.
            # Remove only wrappers around a single atomic null predicate;
            # grouping around AND/OR expressions remains intact.
            pieces.append(inner if is_atomic_predicate(inner) else f"({inner})")
            index = closing + 1
        return "".join(pieces)

    normalized = normalize_nested_groups(strip_outer(value))
    compact = []
    index = 0
    while index < len(normalized):
        if normalized[index] in ("'", '"'):
            quote = normalized[index]
            end = index + 1
            while end < len(normalized):
                if normalized[end] == quote:
                    if end + 1 < len(normalized) and normalized[end + 1] == quote:
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            compact.append(normalized[index:end])
            index = end
        elif normalized[index].isspace():
            index += 1
        else:
            compact.append(normalized[index])
            index += 1
    return "".join(compact)


def _create_table_specs(statement):
    match = re.match(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?\s*\((.*)\)\s*(ENGINE\s*=.*)$",
        statement, re.I | re.S,
    )
    if not match:
        raise MigrationError("Cannot safely inspect CREATE TABLE statement.")
    table = match.group(1)
    options = match.group(3)
    engine = re.search(r"\bENGINE\s*=\s*([\w]+)", options, re.I)
    charset = re.search(r"\b(?:DEFAULT\s+)?(?:CHARSET|CHARACTER\s+SET)\s*=?\s*([\w]+)", options, re.I)
    collation = re.search(r"\bCOLLATE\s*=?\s*([\w]+)", options, re.I)
    if not engine:
        raise MigrationError(f"Cannot safely inspect storage engine for table {table}.")
    table_definition = (
        engine.group(1).lower(),
        charset.group(1).lower() if charset else None,
        collation.group(1).lower() if collation else None,
    )
    specs = [ObjectSpec("table", table, table, table_definition)]
    for clause in _split_top_level(match.group(2)):
        if re.match(r"^(PRIMARY\s+KEY|UNIQUE\s+(?:KEY|INDEX)|(?:KEY|INDEX))\b", clause, re.I):
            index = re.match(r"^(UNIQUE\s+)?(?:KEY|INDEX)\s+`?(\w+)`?\s*\(([^)]*)\)", clause, re.I | re.S)
            primary = re.match(r"^PRIMARY\s+KEY\s*\(([^)]*)\)", clause, re.I | re.S)
            if primary:
                name, unique, raw_columns = "PRIMARY", True, primary.group(1)
            elif index:
                name, unique, raw_columns = index.group(2), bool(index.group(1)), index.group(3)
            else:
                raise MigrationError(f"Cannot safely inspect index clause: {clause}")
            columns = tuple(re.sub(r"`", "", part.strip().split()[0]).lower() for part in raw_columns.split(","))
            specs.append(ObjectSpec("index", table, name, (not unique, columns)))
            continue
        constraint = re.match(r"^CONSTRAINT\s+`?(\w+)`?\s+(.+)$", clause, re.I | re.S)
        if constraint:
            specs.append(_clause_spec(table, f"ADD CONSTRAINT {constraint.group(1)} {constraint.group(2)}"))
            continue
        column_name = re.match(r"^`?(\w+)`?\s+", clause)
        if not column_name:
            raise MigrationError(f"Cannot safely inspect CREATE TABLE clause: {clause}")
        specs.append(_column_spec(table, column_name.group(1), clause))
    return tuple(specs)


def parse_action(statement):
    statement = statement.strip().rstrip(";")
    create = re.match(r"CREATE\s+TABLE\b", statement, re.I)
    if create:
        return MigrationAction(statement, _create_table_specs(statement))
    alter = re.match(r"ALTER\s+TABLE\s+`?(\w+)`?\s+(.*)$", statement, re.I | re.S)
    if alter:
        table, clauses = alter.group(1), _split_top_level(alter.group(2))
        specs = []
        for clause in clauses:
            specs.append(_clause_spec(table, clause))
        return MigrationAction(statement, tuple(specs), tuple(clauses))
    create_index = re.match(r"CREATE\s+(UNIQUE\s+)?INDEX\s+`?(\w+)`?\s+ON\s+`?(\w+)`?\s*\(([^)]*)\)", statement, re.I | re.S)
    if create_index:
        columns = tuple(re.sub(r"`", "", part.strip().split()[0]).lower() for part in create_index.group(4).split(","))
        spec = ObjectSpec("index", create_index.group(3), create_index.group(2), (not bool(create_index.group(1)), columns))
        return MigrationAction(statement, (spec,))
    raise MigrationError(f"Unsupported migration statement; refusing to skip it: {statement[:120]}")


def _fetchall(cur, query, params):
    cur.execute(query, params)
    return cur.fetchall()


def _object_state(cur, spec):
    if spec.kind == "table":
        rows = _fetchall(
            cur,
            "SELECT t.TABLE_NAME,t.ENGINE,t.TABLE_COLLATION,c.CHARACTER_SET_NAME "
            "FROM information_schema.TABLES t "
            "LEFT JOIN information_schema.COLLATION_CHARACTER_SET_APPLICABILITY c "
            "ON c.COLLATION_NAME=t.TABLE_COLLATION "
            "WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_NAME=%s",
            (spec.table,),
        )
        if not rows:
            return False
        expected = spec.definition
        if not expected:
            return True
        row = rows[0]
        actual = (
            (row.get("ENGINE") or "").lower() or None if expected[0] else None,
            (row.get("CHARACTER_SET_NAME") or "").lower() or None if expected[1] else None,
            (row.get("TABLE_COLLATION") or "").lower() or None if expected[2] else None,
        )
        return _require_match(spec, actual, row)
    if spec.kind == "column":
        if not _table_exists(cur, spec.table):
            raise MigrationError(
                f"Required table {spec.table} is missing while checking column {spec.name}. "
                "This migration's base schema is incomplete; restore or repair it manually before continuing."
            )
        rows = _fetchall(cur, "SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s", (spec.table, spec.name))
        if not rows:
            return False
        row = rows[0]
        actual_type = re.sub(r"\s+", "", row["COLUMN_TYPE"]).lower()
        if actual_type in {"integer", "int(11)", "int(10)"}:
            actual_type = "int"
        actual = (
            actual_type,
            row["IS_NULLABLE"] == "YES",
            _normalize_default(row.get("COLUMN_DEFAULT")),
            "auto_increment" in (row.get("EXTRA") or "").lower(),
            (re.search(r"on update (current_timestamp(?:\(\))?)", row.get("EXTRA", ""), re.I).group(1).lower()
             if re.search(r"on update (current_timestamp(?:\(\))?)", row.get("EXTRA", ""), re.I) else None),
        )
        return _require_match(spec, actual, rows[0])
    if spec.kind == "index":
        if not _table_exists(cur, spec.table):
            raise MigrationError(f"Required table {spec.table} is missing while checking index {spec.name}.")
        rows = _fetchall(cur, "SELECT INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s ORDER BY SEQ_IN_INDEX", (spec.table, spec.name))
        if not rows:
            return False
        actual = (bool(rows[0]["NON_UNIQUE"]), tuple(row["COLUMN_NAME"].lower() for row in rows))
        return _require_match(spec, actual, rows)
    if spec.kind == "foreign_key":
        if not _table_exists(cur, spec.table):
            raise MigrationError(f"Required table {spec.table} is missing while checking foreign key {spec.name}.")
        rows = _fetchall(cur, "SELECT k.COLUMN_NAME,k.REFERENCED_TABLE_NAME,k.REFERENCED_COLUMN_NAME,r.DELETE_RULE FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON r.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME=k.CONSTRAINT_NAME WHERE k.CONSTRAINT_SCHEMA=DATABASE() AND k.TABLE_NAME=%s AND k.CONSTRAINT_NAME=%s ORDER BY k.ORDINAL_POSITION", (spec.table, spec.name))
        if not rows:
            return False
        actual = (tuple(row["COLUMN_NAME"].lower() for row in rows), rows[0]["REFERENCED_TABLE_NAME"].lower(), tuple(row["REFERENCED_COLUMN_NAME"].lower() for row in rows), _normalize_delete_rule(rows[0]["DELETE_RULE"]))
        return _require_match(spec, actual, rows)
    if spec.kind == "check":
        if not _table_exists(cur, spec.table):
            raise MigrationError(f"Required table {spec.table} is missing while checking check constraint {spec.name}.")
        rows = _fetchall(cur, "SELECT cc.CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc ON tc.CONSTRAINT_SCHEMA=cc.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=cc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA=DATABASE() AND tc.TABLE_NAME=%s AND tc.CONSTRAINT_NAME=%s AND tc.CONSTRAINT_TYPE='CHECK'", (spec.table, spec.name))
        if not rows:
            return False
        actual = (_normalize_expression(rows[0]["CHECK_CLAUSE"]),)
        return _require_match(spec, actual, rows)
    raise MigrationError(f"Unknown schema object type: {spec.kind}")


def _require_match(spec, actual, evidence):
    matches = actual == spec.definition
    if spec.kind == "foreign_key" and len(actual) == len(spec.definition) == 4:
        actual_rule = _normalize_delete_rule(actual[3])
        expected_rule = _normalize_delete_rule(spec.definition[3])
        matches = actual[:3] == spec.definition[:3] and actual_rule == expected_rule
    if spec.kind == "column" and len(actual) == len(spec.definition) == 5:
        # MySQL 8.0 information_schema.COLUMNS does not distinguish an
        # implicit NULL default from an explicit DEFAULT NULL. Its NULL
        # COLUMN_DEFAULT is therefore consistent with either parsed state.
        expected_default = spec.definition[2]
        if expected_default != NO_DEFAULT:
            # Normalize expectations too, so ObjectSpecs created by older or
            # alternate parsing paths cannot compare SQL's "null" to None.
            expected_default = _normalize_default(expected_default)
        matches = actual[:2] == spec.definition[:2] and actual[3:] == spec.definition[3:]
        matches = matches and (
            _column_defaults_equal(spec.definition[0], expected_default, actual[2])
            or (actual[2] is None and expected_default == NO_DEFAULT)
        )
    if not matches:
        raise MigrationError(
            f"Schema conflict for {spec.kind} {spec.table}.{spec.name}: "
            f"found {evidence!r}, expected definition {spec.definition!r}. "
            "No automatic repair was attempted. Review the schema and migration history manually."
        )
    return True


def _table_exists(cur, table):
    rows = _fetchall(cur, "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (table,))
    return bool(rows)


def _table_names(cur):
    rows = _fetchall(
        cur,
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'",
        (),
    )
    return {row["TABLE_NAME"] for row in rows}


def _preflight_baseline(cur, actions, recorded, confirm_baseline_recovery):
    """Classify baseline state before any legacy-table DDL can run."""
    if BASELINE_VERSION in recorded:
        return

    baseline_tables = [spec.table for action in actions for spec in action.objects if spec.kind == "table"]
    missing = []
    for action in actions:
        table_spec = next((spec for spec in action.objects if spec.kind == "table"), None)
        if not table_spec:
            raise MigrationError("The legacy baseline must use CREATE TABLE actions only.")
        if _table_exists(cur, table_spec.table):
            # Validate every existing base table before allowing any missing table to be created.
            _missing_objects(cur, action)
        else:
            missing.append(table_spec.table)

    later_versions = recorded - {BASELINE_VERSION}
    if later_versions and missing:
        raise MigrationError(
            "Legacy baseline schema drift: a base table is missing while later migration "
            f"version(s) are recorded ({', '.join(sorted(later_versions))}). "
            "No baseline DDL was executed; review and repair the schema manually."
        )

    if missing:
        existing_application_tables = _table_names(cur) - {"schema_migrations"}
        fresh_empty_schema = not existing_application_tables and not any(
            _table_exists(cur, table) for table in baseline_tables
        )
        if not fresh_empty_schema and not confirm_baseline_recovery:
            raise MigrationError(
                "Ambiguous legacy baseline state: some base tables are missing while other "
                "application tables exist. No baseline DDL was executed. Verify this is a "
                "disposable/partial initialization, then rerun with --confirm-baseline-recovery."
            )


def _verified(cur, action):
    return not _missing_objects(cur, action)


def _missing_objects(cur, action):
    table_spec = next((spec for spec in action.objects if spec.kind == "table"), None)
    if table_spec:
        if not _object_state(cur, table_spec):
            return list(action.objects)
        for spec in action.objects:
            if spec.kind != "table" and not _object_state(cur, spec):
                raise MigrationError(
                    f"Existing table {table_spec.table} is missing expected {spec.kind} "
                    f"{spec.name}; refusing CREATE TABLE IF NOT EXISTS as a repair. "
                    "Inspect the database and perform a reviewed manual recovery."
                )
        return []
    return [spec for spec in action.objects if not _object_state(cur, spec)]


def _sql_for_missing_objects(action, missing):
    if not action.clauses or len(missing) == len(action.objects):
        return action.sql
    missing_keys = {(spec.kind, spec.table.lower(), spec.name.lower()) for spec in missing}
    clauses = [clause for spec, clause in zip(action.objects, action.clauses)
               if (spec.kind, spec.table.lower(), spec.name.lower()) in missing_keys]
    table_match = re.match(r"ALTER\s+TABLE\s+`?(\w+)`?", action.sql, re.I)
    if not table_match or not clauses:
        raise MigrationError("Unable to construct a safe DDL statement for the missing migration objects.")
    return f"ALTER TABLE `{table_match.group(1)}` " + ", ".join(clauses)


def _statements(path):
    sql = _strip_comments(path.read_text(encoding="utf-8"))
    return [part.strip() for part in sql.split(";") if part.strip()]


def _migration_actions(path):
    actions = []
    for statement in _statements(path):
        parsed = parse_action(statement)
        actions.extend(parsed if isinstance(parsed, tuple) else (parsed,))
    return actions


def _check_recorded_migration(cur, path, actions):
    for index, action in enumerate(actions, 1):
        if not _verified(cur, action):
            raise MigrationError(
                f"Migration {path.name} is recorded as applied, but expected schema object(s) "
                f"for step {index} are missing. This is schema drift; no DDL was executed. "
                "Restore from a verified backup or perform a reviewed manual repair before retrying."
            )


def run(conn=None, migrations_dir=None, confirm_baseline_recovery=False):
    """Apply or resume migrations after verifying each schema object.

    Passing a connection and directory allows database-free/mock verification.
    The CLI continues to use the configured database connection.
    """
    owned_connection = conn is None
    conn = conn or connect()
    migrations_dir = Path(migrations_dir or MIGRATIONS)
    cur = conn.cursor(dictionary=True)
    current_version = None
    try:
        metadata_action = parse_action(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(100) NOT NULL PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB"
        )
        if not _verified(cur, metadata_action):
            cur.execute(metadata_action.sql)
            conn.commit()
            if not _verified(cur, metadata_action):
                raise MigrationError("schema_migrations bootstrap ran but its structure did not verify.")
        cur.execute("SELECT version FROM schema_migrations")
        recorded = {row["version"] for row in cur.fetchall()}
        paths = sorted(migrations_dir.glob("*.sql"))
        baseline_path = next((path for path in paths if path.name == BASELINE_VERSION), None)
        if baseline_path:
            _preflight_baseline(
                cur, _migration_actions(baseline_path), recorded, confirm_baseline_recovery,
            )
        for path in paths:
            version = path.name
            current_version = version
            actions = _migration_actions(path)
            if version in recorded:
                _check_recorded_migration(cur, path, actions)
                print(f"Already applied and verified: {version}")
                continue

            print(f"Applying or recovering migration: {version}")
            for index, action in enumerate(actions, 1):
                missing = _missing_objects(cur, action)
                if not missing:
                    print(f"Verified existing/completed schema step {index}/{len(actions)}: {version}")
                    continue
                try:
                    cur.execute(_sql_for_missing_objects(action, missing))
                    conn.commit()
                except Exception as error:
                    conn.rollback()
                    raise MigrationError(
                        f"Migration {version} failed at schema step {index}/{len(actions)}: {error}. "
                        "MySQL may have committed earlier DDL. No migration version was recorded. "
                        "Do not edit or drop objects blindly: fix the reported cause, verify the target "
                        "database, then rerun; completed matching objects will be verified and skipped. "
                        "For conflicting definitions, stop and perform a reviewed manual recovery."
                    ) from error
                if not _verified(cur, action):
                    raise MigrationError(
                        f"Migration {version} step {index}/{len(actions)} ran but its expected schema "
                        "did not verify. No migration version was recorded; inspect the schema manually."
                    )

            _check_recorded_migration(cur, path, actions)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            conn.commit()
            recorded.add(version)
            print(f"Applied and verified: {version}")
        return True
    except Exception as error:
        conn.rollback()
        if isinstance(error, MigrationError):
            raise
        context = f" while processing {current_version}" if current_version else ""
        raise MigrationError(f"Migration runner failed{context}: {error}") from error
    finally:
        cur.close()
        if owned_connection:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify and apply additive FitTrack MySQL migrations.")
    parser.add_argument(
        "--confirm-baseline-recovery", action="store_true",
        help="confirm the target is a reviewed partial/ambiguous baseline initialization",
    )
    parser.add_argument(
        "--confirm-production", action="store_true",
        help="confirm a reviewed production migration to FITTRACK_EXPECTED_DB_HOST/FITTRACK_EXPECTED_DB_NAME",
    )
    args = parser.parse_args()
    if _environment in {"prod", "production"} and not args.confirm_production:
        raise SystemExit("Production migration requires --confirm-production and FITTRACK_EXPECTED_DB_NAME.")
    try:
        run(confirm_baseline_recovery=args.confirm_baseline_recovery)
    except Exception as exc:
        print(f"Migration stopped safely: {exc}", file=sys.stderr)
        raise
