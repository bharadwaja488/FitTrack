"""Opt-in integration test for the configured local MySQL database.

Run with FITTRACK_RUN_DB_TESTS=1. Test accounts and rows are uniquely named and
removed in a finally block.
"""
import os
import re
import sys
import uuid
from contextlib import nullcontext
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.database import connection
from app.services.account_service import delete_account


TEST_CONFIRMATION = "I_CONFIRM_THIS_IS_A_DISPOSABLE_TEST_DATABASE"


def build_test_database_config(env):
    """Return an explicit test-only connection config; never inherit .env DB values."""
    required = {
        "FITTRACK_TEST_DB_NAME": env.get("FITTRACK_TEST_DB_NAME", "").strip(),
        "FITTRACK_TEST_DB_HOST": env.get("FITTRACK_TEST_DB_HOST", "").strip(),
        "FITTRACK_TEST_DB_USER": env.get("FITTRACK_TEST_DB_USER", "").strip(),
        "FITTRACK_TEST_DB_PASSWORD": env.get("FITTRACK_TEST_DB_PASSWORD", ""),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError("MySQL integration requires explicit FITTRACK_TEST_DB_NAME, HOST, USER, and PASSWORD settings.")
    name = required["FITTRACK_TEST_DB_NAME"]
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", name.lower())))
    if "test" not in tokens or tokens.intersection({"prod", "production", "live"}) or name.lower() == "fittrack":
        raise ValueError("FITTRACK_TEST_DB_NAME must be a dedicated test database name and cannot be production-like.")
    if env.get("FITTRACK_TEST_DB_CONFIRM") != TEST_CONFIRMATION:
        raise ValueError("Set FITTRACK_TEST_DB_CONFIRM to the documented test-only confirmation before running MySQL integration.")
    return {
        "DB_NAME": name,
        "DB_HOST": required["FITTRACK_TEST_DB_HOST"],
        "DB_USER": required["FITTRACK_TEST_DB_USER"],
        "DB_PASSWORD": required["FITTRACK_TEST_DB_PASSWORD"],
    }


def _register_and_track_account(client, name, email, mutate, find_account_id, account_ids, password):
    response = mutate(client, "post", "/api/auth/register", {
        "full_name": name, "email": email, "password": password, "confirm_password": password,
    })
    assert response.status_code == 202, response.json
    account_id = find_account_id(email)
    assert account_id is not None, "Registered test account could not be identified for cleanup."
    account_ids.append(account_id)
    login = mutate(client, "post", "/api/auth/login", {"email": email, "password": password})
    assert login.status_code == 200, login.json
    return login


def _cleanup_created_accounts(app, account_ids, password, delete=delete_account):
    with app.app_context():
        for account_id in reversed(account_ids):
            delete(account_id, password)


def test_registration_followed_by_login_failure_still_cleans_up_created_account():
    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self.json = payload or {}

    app = type("AppContext", (), {"app_context": staticmethod(nullcontext)})()
    account_ids, calls, delete = [], [], Mock()

    def mutate(_client, method, path, _data):
        calls.append((method, path))
        return Response(202) if path == "/api/auth/register" else Response(401, {"error": "login failed"})

    try:
        with pytest.raises(AssertionError):
            _register_and_track_account(
                object(), "Disposable", "fittrack-test-unit@example.com", mutate,
                lambda _email: 987654321, account_ids, "test-only-password",
            )
    finally:
        _cleanup_created_accounts(app, account_ids, "test-only-password", delete)

    assert calls == [("post", "/api/auth/register"), ("post", "/api/auth/login")]
    assert account_ids == [987654321]
    delete.assert_called_once_with(987654321, "test-only-password")


def test_mysql_integration_requires_explicit_disposable_database_config():
    with pytest.raises(ValueError, match="explicit FITTRACK_TEST_DB"):
        build_test_database_config({})


@pytest.mark.parametrize("name", ["fittrack", "fittrack_prod", "production_test", "live_test"])
def test_mysql_integration_rejects_production_like_database_names(name):
    env = {
        "FITTRACK_TEST_DB_NAME": name,
        "FITTRACK_TEST_DB_HOST": "127.0.0.1",
        "FITTRACK_TEST_DB_USER": "test_user",
        "FITTRACK_TEST_DB_PASSWORD": "test_password",
        "FITTRACK_TEST_DB_CONFIRM": TEST_CONFIRMATION,
    }
    with pytest.raises(ValueError, match="dedicated test database"):
        build_test_database_config(env)


def test_mysql_integration_accepts_only_explicitly_confirmed_test_database():
    env = {
        "FITTRACK_TEST_DB_NAME": "fittrack_test_20261115",
        "FITTRACK_TEST_DB_HOST": "127.0.0.1",
        "FITTRACK_TEST_DB_USER": "test_user",
        "FITTRACK_TEST_DB_PASSWORD": "test_password",
        "FITTRACK_TEST_DB_CONFIRM": TEST_CONFIRMATION,
        "DB_NAME": "fittrack",
    }
    config = build_test_database_config(env)
    assert config["DB_NAME"] == "fittrack_test_20261115"
    assert "fittrack" != config["DB_NAME"]


@pytest.mark.skipif(os.getenv("FITTRACK_RUN_DB_TESTS") != "1", reason="Set FITTRACK_RUN_DB_TESTS=1 for the MySQL integration test")
def test_two_accounts_cannot_read_or_write_each_others_fitness_data():
    try:
        test_db_config = build_test_database_config(os.environ)
    except ValueError as error:
        pytest.fail(f"Refusing MySQL integration test: {error}")

    app = create_app()
    # Override every database connection value with explicit test-only values.
    # The application .env database is never a fallback.
    app.config.update(test_db_config)
    clients = [app.test_client(), app.test_client()]
    password = "FitTrackIntegration2026"
    emails = [f"fittrack-test-{uuid.uuid4().hex}@example.com" for _ in clients]
    account_ids = []

    # Confirm the server-selected schema before the test can create anything.
    with app.app_context():
        with connection() as (_, cur):
            cur.execute("SELECT DATABASE() AS selected_database")
            selected = cur.fetchone()["selected_database"]
        if selected != test_db_config["DB_NAME"]:
            pytest.fail("Refusing MySQL integration test: selected database does not match the explicitly configured test database.")

    def mutate(client, method, path, data):
        token = client.get("/api/auth/csrf").json["data"]["csrf_token"]
        return getattr(client, method)(path, json=data, headers={"X-CSRF-Token": token})

    def find_account_id(email):
        with app.app_context(), connection() as (_, cur):
            cur.execute("SELECT account_id FROM accounts WHERE email=%s", (email,))
            row = cur.fetchone()
        return row["account_id"] if row else None

    try:
        for client, name, email in zip(clients, ("Integration One", "Integration Two"), emails):
            assert find_account_id(email) is None, "Generated integration email unexpectedly already exists."
            login = _register_and_track_account(
                client, name, email, mutate, find_account_id, account_ids, password,
            )
            assert login.json["data"]["account"]["account_id"] == account_ids[-1]
        for client, name in zip(clients, ("Integration One", "Integration Two")):
            response = mutate(client, "put", "/api/profile", {
                "full_name": name, "age": 31, "gender": "female", "height": 1.66,
                "weight": 62, "activity_level": "moderate",
            })
            assert response.status_code == 200, response.json

        goal_response = mutate(clients[0], "put", "/api/fitness/step-goal", {"daily_step_goal": 10000})
        assert goal_response.status_code == 200
        assert mutate(clients[0], "put", "/api/fitness/step-goal", {"daily_step_goal": 10000}).status_code == 200
        assert clients[0].get("/api/fitness/step-goal").json["data"]["daily_step_goal"] == 10000
        assert clients[1].get("/api/fitness/step-goal").json["data"]["daily_step_goal"] is None
        assert mutate(clients[0], "put", "/api/fitness/step-goal", {"daily_step_goal": 10000.5}).status_code == 400

        base_date = date.today()
        daily = mutate(clients[0], "post", "/api/fitness", {
            "record_type": "daily", "record_date": base_date.isoformat(), "steps": 6000,
        })
        assert daily.status_code == 201, daily.json
        daily_id = daily.json["data"]["record_id"]
        cardio = mutate(clients[0], "post", "/api/fitness", {
            "record_type": "cardio", "record_date": base_date.isoformat(), "activity_type": "walking",
            "distance": 5, "workout_minutes": 30, "calories_burned": 150, "notes": "Park walk",
        })
        assert cardio.status_code == 201, cardio.json
        cardio_id = cardio.json["data"]["record_id"]
        assert cardio.json["data"]["average_pace_min_per_km"] == 6
        workout = mutate(clients[0], "post", "/api/fitness", {
            "record_type": "workout", "record_date": base_date.isoformat(),
            "workout_category": "strength_training", "workout_name": "Upper body", "workout_minutes": 40,
        })
        assert workout.status_code == 201, workout.json
        workout_id = workout.json["data"]["record_id"]
        assert workout.json["data"]["calories_burned"] is None
        foreign_cardio_id = cardio_id
        assert mutate(clients[1], "put", f"/api/fitness/{foreign_cardio_id}", {
            **cardio.json["data"], "record_date": base_date.isoformat(),
        }).status_code == 404
        assert mutate(clients[1], "delete", f"/api/fitness/{foreign_cardio_id}", {}).status_code == 404
        edited_cardio = mutate(clients[0], "put", f"/api/fitness/{cardio_id}", {
            "record_type": "cardio", "record_date": base_date.isoformat(), "activity_type": "running",
            "distance": 6, "workout_minutes": 30, "calories_burned": 180,
        })
        assert edited_cardio.status_code == 200
        assert edited_cardio.json["data"]["average_pace_min_per_km"] == 5
        cycling = mutate(clients[0], "post", "/api/fitness", {
            "record_type": "cardio", "record_date": base_date.isoformat(),
            "activity_type": "cycling", "distance": 3.5, "workout_minutes": 25,
        })
        assert cycling.status_code == 201, cycling.json
        assert cycling.json["data"]["average_pace_min_per_km"] is None
        assert cycling.json["data"]["average_speed_kmh"] == 8.4
        assert mutate(clients[0], "delete", f"/api/fitness/{workout_id}", {}).json["data"]["deleted"] is True
        activity_filter = clients[0].get("/api/fitness/history", query_string={
            "start": base_date.isoformat(), "end": base_date.isoformat(),
        })
        assert activity_filter.status_code == 200
        history_rows = activity_filter.json["data"]
        assert len(history_rows) == 3
        running_rows = [row for row in history_rows if row["activity_type"] == "running"]
        cycling_rows = [row for row in history_rows if row["activity_type"] == "cycling"]
        assert len(running_rows) == 1
        assert running_rows[0]["record_id"] == cardio_id
        assert running_rows[0]["average_pace_min_per_km"] == 5
        assert len(cycling_rows) == 1
        assert cycling_rows[0]["record_id"] == cycling.json["data"]["record_id"]
        assert cycling_rows[0]["average_speed_kmh"] == 8.4
        assert clients[0].get("/api/fitness").json["data"]
        assert clients[0].get("/api/fitness/history", query_string={"start": "not-a-date"}).status_code == 400
        assert clients[0].get("/api/fitness/history", query_string={
            "start": base_date.isoformat(), "end": (base_date - timedelta(days=1)).isoformat(),
        }).status_code == 400

        goal_targets = {
            "weight_loss": (55, 300, -300),
            "maintenance": (62, 0, 0),
            "weight_gain": (68, 200, 200),
            "muscle_building": (70, 200, 200),
        }
        for goal_type, (target, adjustment, delta) in goal_targets.items():
            response = mutate(clients[0], "put", "/api/goals", {
                "goal_type": goal_type, "target_weight_kg": target,
                "calorie_adjustment": adjustment, "confirm_calorie_target": True,
            })
            assert response.status_code == 200, response.json
            goal = response.json["data"]["goal"]
            assert goal["goal_type"] == goal_type
            assert goal["starting_weight_kg"] == 62
            assert goal["daily_calorie_target"] == pytest.approx(goal["tdee"] + delta, abs=0.01)
        response = mutate(clients[1], "put", "/api/goals", {
            "goal_type": "maintenance", "target_weight_kg": 62,
            "confirm_calorie_target": False,
        })
        assert response.status_code == 200
        assert response.json["data"]["goal"]["daily_calorie_target"] is None
        with app.app_context(), connection() as (conn, cur):
            cur.execute("UPDATE users SET target_calories=2345 WHERE account_id=%s", (account_ids[1],))
            conn.commit()

        entry_ids = []
        for days_ago, weight in ((35, 63), (7, 62.5), (0, 62)):
            response = mutate(clients[0], "post", "/api/weight", {
                "weight_kg": weight, "recorded_at": (base_date - timedelta(days=days_ago)).isoformat(),
            })
            assert response.status_code == 201, response.json
            entry_ids.append(response.json["data"]["record"]["record_id"])
        response = mutate(clients[1], "post", "/api/weight", {
            "weight_kg": 63.5, "recorded_at": base_date.isoformat(),
        })
        assert response.status_code == 201
        foreign_record_id = response.json["data"]["record"]["record_id"]
        history_a = clients[0].get("/api/weight").json["data"]
        history_b = clients[1].get("/api/weight").json["data"]
        assert len(history_a["records"]) == 3
        assert len(history_b["records"]) == 1
        assert history_a["trend"]["weekly_weight_change_kg"] == pytest.approx(-0.5)
        assert history_a["trend"]["monthly_weight_change_kg"] == pytest.approx(-1.0)
        assert clients[0].put(f"/api/weight/{foreign_record_id}", json={
            "weight_kg": 64, "recorded_at": base_date.isoformat(),
        }, headers={"X-CSRF-Token": clients[0].get("/api/auth/csrf").json["data"]["csrf_token"]}).status_code == 404
        assert mutate(clients[0], "delete", f"/api/weight/{foreign_record_id}", {}).status_code == 404

        corrected = mutate(clients[0], "put", f"/api/weight/{entry_ids[1]}", {
            "weight_kg": 62.25, "recorded_at": (base_date - timedelta(days=7)).isoformat(),
        })
        assert corrected.status_code == 200
        removed = mutate(clients[0], "delete", f"/api/weight/{entry_ids[0]}", {})
        assert removed.status_code == 200
        own_a = clients[0].get("/api/profile").json["data"]["profile"]
        own_b = clients[1].get("/api/profile").json["data"]["profile"]
        assert own_a["name"] == "Integration One" and own_b["name"] == "Integration Two"
        assert "user_id" not in own_a and "user_id" not in own_b

        activity = mutate(clients[0], "post", "/api/fitness", {
            "record_date": base_date.isoformat(), "steps": 4321, "distance": 3.2,
            "workout_minutes": 35, "calories_burned": 240,
            "user_id": 987654321, "account_id": account_ids[1],
        })
        assert activity.status_code == 201, activity.json
        assert len(clients[0].get("/api/fitness/history").json["data"]) == 3
        assert clients[1].get("/api/fitness/history").json["data"] == []
        summary_a = clients[0].get("/api/dashboard/summary").json["data"]
        summary_b = clients[1].get("/api/dashboard/summary").json["data"]
        assert summary_a["steps"] == 10321
        assert summary_b["steps"] == 0
        assert summary_a["bmi_category"] == "Healthy weight"
        assert summary_a["activity_level"] == "moderate"
        assert summary_a["activity_multiplier"] == 1.55
        assert summary_a["tdee"] == pytest.approx(summary_a["bmr"] * 1.55)
        assert summary_a["daily_calorie_target"] == pytest.approx(summary_a["tdee"] + 200, abs=0.01)
        assert summary_a["calories_burned"] == 420
        assert summary_a["steps_today"] == 10321
        assert summary_a["daily_step_goal"] == 10000
        assert summary_a["steps_remaining"] == 0
        assert summary_a["step_goal_percentage"] == pytest.approx(103.2)
        weekly_activity = clients[0].get("/api/dashboard/activity", query_string={"period": "week"}).json["data"]
        today_activity = next(row for row in weekly_activity if row["record_date"] == base_date.isoformat())
        assert today_activity["cardio_distance_km"] == pytest.approx(6)
        profile_a = clients[0].get("/api/profile").json["data"]["profile"]
        assert profile_a["bmi_category"] == "Healthy weight"
        assert profile_a["tdee"] == pytest.approx(profile_a["bmr"] * 1.55)
        assert profile_a["daily_calorie_target"] == pytest.approx(profile_a["tdee"] + 200, abs=0.01)

        assert mutate(clients[0], "patch", "/api/goals/status", {"status": "paused"}).json["data"]["goal"]["status"] == "paused"
        assert mutate(clients[0], "patch", "/api/goals/status", {"status": "active"}).json["data"]["goal"]["status"] == "active"
        completed = mutate(clients[0], "post", "/api/weight", {
            "weight_kg": 70, "recorded_at": date.today().isoformat(),
        })
        assert completed.status_code == 201
        assert clients[0].get("/api/goals").json["data"]["goal"]["status"] == "completed"

        with app.app_context(), connection() as (_, cur):
            cur.execute("SELECT password_hash FROM accounts WHERE account_id=%s", (account_ids[0],))
            assert cur.fetchone()["password_hash"].startswith("$argon2id$")
    finally:
        _cleanup_created_accounts(app, account_ids, password)
