import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.personal_fitness_service import activity_metrics
from app.services import personal_fitness_service
from app.utils.validators import record_values, step_goal_value


def test_history_keeps_same_pace_rows_distinct_by_database_record_id(monkeypatch):
    database_rows = [
        {
            "record_id": 42, "record_date": date(2026, 11, 17), "steps": None,
            "distance": 3.5, "workout_minutes": 25, "calories_burned": None,
            "record_type": "cardio", "activity_type": "running", "workout_category": None,
            "workout_name": None, "notes": None,
        },
        {
            "record_id": 41, "record_date": date(2026, 11, 17), "steps": None,
            "distance": 3.5, "workout_minutes": 25, "calories_burned": None,
            "record_type": "cardio", "activity_type": "walking", "workout_category": None,
            "workout_name": None, "notes": None,
        },
    ]

    class Cursor:
        def execute(self, query, params):
            assert query.endswith("ORDER BY r.record_date DESC,r.record_id DESC")
            assert params == (7,)

        def fetchall(self):
            return [dict(row) for row in database_rows]

    @contextmanager
    def fake_connection():
        yield object(), Cursor()

    monkeypatch.setattr(personal_fitness_service, "connection", fake_connection)
    result = personal_fitness_service.list_records(7)

    assert [(row["record_id"], row["activity_type"]) for row in result] == [
        (42, "running"), (41, "walking"),
    ]
    assert [row["average_pace_min_per_km"] for row in result] == [7.14, 7.14]
    assert [row["average_speed_kmh"] for row in result] == [None, None]


def test_cardio_record_accepts_each_supported_activity_and_calculates_display_metrics():
    for activity_type in ("walking", "running", "jogging", "cycling"):
        row = record_values({
            "record_type": "cardio", "record_date": "2026-11-13", "activity_type": activity_type,
            "distance": 5, "workout_minutes": 30,
        })
        assert row["record_type"] == "cardio"
        assert row["activity_type"] == activity_type
    assert activity_metrics("walking", 5, 30) == {
        "average_pace_min_per_km": 6, "average_speed_kmh": None,
    }
    assert activity_metrics("cycling", 15, 30) == {
        "average_pace_min_per_km": None, "average_speed_kmh": 30,
    }
    assert activity_metrics("running", 0, 30)["average_pace_min_per_km"] is None


def test_daily_steps_and_legacy_fitness_payload_remain_supported():
    daily = record_values({"record_type": "daily", "record_date": "2026-11-13", "steps": "8000"})
    assert daily["steps"] == 8000
    legacy = record_values({
        "record_date": "2026-11-13", "steps": 4321, "distance": 3.2,
        "workout_minutes": 35, "calories_burned": 240,
    })
    assert legacy["record_type"] == "daily"
    assert legacy["steps"] == 4321
    assert legacy["distance"] == 3.2


def test_workout_record_supports_each_category_and_optional_calories():
    for category in ("strength_training", "cardio", "calisthenics", "yoga", "other"):
        workout = record_values({
            "record_type": "workout", "record_date": "2026-11-13",
            "workout_category": category, "workout_name": "Session", "workout_minutes": 45,
            "notes": "Optional note",
        })
        assert workout["workout_category"] == category
        assert workout["calories_burned"] is None


@pytest.mark.parametrize("payload", [
    {"record_type": "daily", "record_date": "2026-11-13", "steps": -1},
    {"record_type": "daily", "record_date": "2026-11-13", "steps": 1.5},
    {"record_type": "cardio", "record_date": "2026-11-13", "activity_type": "swimming", "distance": 1, "workout_minutes": 10},
    {"record_type": "cardio", "record_date": "2026-11-13", "activity_type": "running", "distance": 0, "workout_minutes": 10},
    {"record_type": "cardio", "record_date": "2026-11-13", "activity_type": "running", "distance": 1, "workout_minutes": 0},
    {"record_type": "workout", "record_date": "2026-11-13", "workout_category": "unknown", "workout_name": "Session", "workout_minutes": 20},
    {"record_type": "workout", "record_date": "2026-11-13", "workout_category": "yoga", "workout_name": "", "workout_minutes": 20},
    {"record_type": "workout", "record_date": "2026-11-13", "workout_category": "yoga", "workout_name": "Yoga", "workout_minutes": 20, "notes": "x" * 501},
    {"record_type": "daily", "record_date": "2026-02-30", "steps": 100},
    {"record_type": "daily", "record_date": (date.today() + timedelta(days=1)).isoformat(), "steps": 100},
])
def test_invalid_activity_payloads_are_rejected(payload):
    with pytest.raises(ValueError):
        record_values(payload)


@pytest.mark.parametrize("value", [0, -1, 100001, 4.5, True, "not a number"])
def test_invalid_daily_step_goals_are_rejected(value):
    with pytest.raises(ValueError):
        step_goal_value({"daily_step_goal": value})


@pytest.mark.parametrize("value", [5000, "10000"])
def test_valid_daily_step_goals_are_accepted(value):
    assert step_goal_value({"daily_step_goal": value}) == int(value)
