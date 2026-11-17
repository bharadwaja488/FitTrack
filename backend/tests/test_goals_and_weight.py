from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.services.goal_service import calorie_suggestion, goal_reached
from app.services import goal_service
from app.services.progress_service import goal_progress, weight_trend
from app.services.weight_service import validate_weight
from app import create_app
from app.routes.goals import date_bounds


@pytest.mark.parametrize("goal,adjustment,expected", [
    ("weight_loss", 300, 2700),
    ("maintenance", 0, 3000),
    ("weight_gain", 200, 3200),
    ("muscle_building", 200, 3200),
])
def test_goal_calorie_suggestions_are_explicit_and_separate(goal, adjustment, expected):
    result = calorie_suggestion(3000, goal, adjustment)
    assert result["suggested_target"] == pytest.approx(expected)
    assert result["calorie_adjustment"] == adjustment


@pytest.mark.parametrize("goal,adjustment", [
    ("weight_loss", 99), ("weight_loss", 501),
    ("weight_gain", 301), ("muscle_building", float("inf")),
    ("unsupported", 200),
])
def test_goal_calorie_suggestion_rejects_unsafe_or_invalid_values(goal, adjustment):
    with pytest.raises(ValueError):
        calorie_suggestion(3000, goal, adjustment)


@pytest.mark.parametrize("value", [None, "", "abc", True, 0, 0.99, 500.01, float("nan"), float("inf")])
def test_weight_input_validation_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_weight(value)


@pytest.mark.parametrize("value", [1, 45, 72.25, 500])
def test_weight_input_validation_accepts_supported_range(value):
    assert validate_weight(value) == float(value)


def test_weight_loss_and_gain_progress_use_direction_correctly():
    loss = goal_progress({"goal_type": "weight_loss", "starting_weight_kg": 90, "target_weight_kg": 70}, 80, [])
    assert loss["total_weight_lost_kg"] == 10
    assert loss["total_weight_gained_kg"] == 0
    assert loss["remaining_to_target_kg"] == 10
    assert loss["progress_percentage"] == 50

    gain = goal_progress({"goal_type": "muscle_building", "starting_weight_kg": 60, "target_weight_kg": 80}, 70, [])
    assert gain["total_weight_lost_kg"] == 0
    assert gain["total_weight_gained_kg"] == 10
    assert gain["remaining_to_target_kg"] == 10
    assert gain["progress_percentage"] == 50


def test_maintenance_reports_stability_and_deviation_without_fake_percentage():
    goal = {"goal_type": "maintenance", "starting_weight_kg": 75, "target_weight_kg": 75}
    stable = goal_progress(goal, 75.4, [])
    above = goal_progress(goal, 76.2, [])
    assert stable["maintenance_status"] == "stable"
    assert stable["remaining_to_target_kg"] == pytest.approx(0.4)
    assert stable["progress_percentage"] is None
    assert above["maintenance_status"] == "above_target"
    assert above["remaining_to_target_kg"] == pytest.approx(1.2)


def test_weight_change_requires_real_records_near_period_cutoffs():
    now = datetime(2026, 11, 10, 12)
    records = [
        {"recorded_at": now - timedelta(days=35), "weight_kg": 80},
        {"recorded_at": now - timedelta(days=7), "weight_kg": 78},
        {"recorded_at": now, "weight_kg": 77.5},
    ]
    trend = weight_trend(records)
    assert trend["weekly_weight_change_kg"] == pytest.approx(-0.5)
    assert trend["monthly_weight_change_kg"] == pytest.approx(-2.5)
    assert weight_trend(records[-1:])["weekly_weight_change_kg"] is None
    assert weight_trend([])["monthly_weight_change_kg"] is None


def test_goal_completion_direction():
    assert goal_reached("weight_loss", 69, 70)
    assert not goal_reached("weight_loss", 71, 70)
    assert goal_reached("weight_gain", 71, 70)
    assert goal_reached("muscle_building", 71, 70)
    assert not goal_reached("maintenance", 70, 70)


def test_goal_service_rejects_weight_loss_target_equal_to_starting_weight_before_write(monkeypatch):
    executed = []

    class Cursor:
        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchone(self):
            return {
                "user_id": 7, "weight": 62, "height": 1.66, "age": 31,
                "gender": "female", "activity_level": "moderate",
            }

    @contextmanager
    def fake_connection():
        yield type("Connection", (), {"commit": lambda self: None})(), Cursor()

    monkeypatch.setattr(goal_service, "connection", fake_connection)
    with pytest.raises(ValueError, match="A weight-loss target must be below your starting weight"):
        goal_service.create_or_update_goal(23, {
            "goal_type": "weight_loss",
            "target_weight_kg": 62,
            "calorie_adjustment": 300,
            "confirm_calorie_target": True,
        })

    assert len(executed) == 1
    assert executed[0][0].startswith("SELECT user_id,weight")


def test_goal_service_accepts_and_persists_valid_weight_loss_target(monkeypatch):
    executed = []
    commits = []

    class Cursor:
        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchone(self):
            return {
                "user_id": 7, "weight": 62, "height": 1.66, "age": 31,
                "gender": "female", "activity_level": "moderate",
            }

    class Connection:
        def commit(self):
            commits.append(True)

    @contextmanager
    def fake_connection():
        yield Connection(), Cursor()

    expected = {"goal": {
        "goal_type": "weight_loss", "target_weight_kg": 55,
        "calorie_adjustment": 300, "daily_calorie_target": 1779.325,
    }}
    monkeypatch.setattr(goal_service, "connection", fake_connection)
    monkeypatch.setattr(goal_service, "get_goal", lambda account_id: expected)
    result = goal_service.create_or_update_goal(23, {
        "goal_type": "weight_loss",
        "target_weight_kg": 55,
        "calorie_adjustment": 300,
        "confirm_calorie_target": True,
    })

    insert = next((params for query, params in executed if query.startswith("INSERT INTO fitness_goals")), None)
    assert insert is not None
    assert insert[1] == "weight_loss"
    assert insert[3] == 55
    assert insert[4] == 300
    assert insert[5] == pytest.approx(1779.325)
    assert commits == [True]
    assert result["goal"]["goal_type"] == "weight_loss"
    assert result["goal"]["target_weight_kg"] == 55
    assert result["goal"]["calorie_adjustment"] == 300
    assert result["goal"]["daily_calorie_target"] == pytest.approx(1779.325)


@pytest.mark.parametrize("query", ["?start=20260101", "?start=2026-11-14&end=2026-11-13"])
def test_weight_date_filters_reject_noncanonical_or_reversed_ranges(query):
    app = create_app()
    with app.test_request_context(f"/api/weight{query}"):
        with pytest.raises(ValueError):
            date_bounds()


def test_weight_date_filters_accept_same_day():
    app = create_app()
    with app.test_request_context("/api/weight?start=2026-11-13&end=2026-11-13"):
        start, end = date_bounds()
    assert (end - start).days == 1
