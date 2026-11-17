from datetime import date
from math import isfinite


def body_json():
    from flask import request
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required.")
    return data


def number(data, key, minimum=None, integer=False):
    if key not in data or data[key] in (None, ""):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} is required.")
    if isinstance(data[key], bool):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be numeric.")
    try:
        value = float(data[key])
    except (TypeError, ValueError):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be numeric.")
    if not isfinite(value) or (integer and not value.is_integer()):
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a whole number." if integer else f"{key.replace('_', ' ').capitalize()} must be numeric.")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be at least {minimum}.")
    return int(value) if integer else value


def user_values(data):
    name = str(data.get("name", "")).strip()
    gender = str(data.get("gender", "")).strip()
    if not name or len(name) > 100:
        raise ValueError("Name is required and must be at most 100 characters.")
    if gender.lower() not in ("male", "female"):
        raise ValueError("Gender must be Male or Female, matching the existing calculation rules.")
    return name, number(data, "age", 1, True), gender, number(data, "height", 0.01), number(data, "weight", 0.01)


def profile_values(data):
    name = str(data.get("full_name", "")).strip()
    gender = str(data.get("gender", "")).strip()
    activity_level = str(data.get("activity_level", "")).strip().lower()
    if not name or len(name) > 100:
        raise ValueError("Full name is required and must be 100 characters or fewer.")
    if gender.lower() not in ("male", "female"):
        raise ValueError("Gender must be Male or Female, matching the existing calculation rules.")
    if activity_level not in {"sedentary", "light", "moderate", "active", "very_active"}:
        raise ValueError("Choose a valid activity level.")
    age = number(data, "age", 1, True)
    height = number(data, "height", 0.01)
    weight = number(data, "weight", 1)
    if age > 120 or height > 3 or weight > 500:
        raise ValueError("Check age, height, and weight values.")
    return name, age, gender, height, weight, activity_level


def record_values(data):
    try:
        raw_date = str(data.get("record_date", ""))
        record_date = date.fromisoformat(raw_date)
    except ValueError:
        raise ValueError("Record date must use YYYY-MM-DD format.")
    if record_date.isoformat() != raw_date:
        raise ValueError("Record date must use YYYY-MM-DD format.")
    if record_date > date.today():
        raise ValueError("Activity records cannot be dated in the future.")

    record_type = str(data.get("record_type") or "daily").strip().lower()
    if record_type not in {"daily", "cardio", "workout"}:
        raise ValueError("Choose a valid activity record type.")

    def optional_number(key, minimum=0, integer=False):
        if data.get(key) in (None, ""):
            return None
        value = number(data, key, minimum, integer)
        if integer and str(data[key]).strip() not in {str(value), f"{value}.0"}:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a whole number.")
        return value

    steps = optional_number("steps", 0, True)
    distance = optional_number("distance", 0)
    duration = optional_number("workout_minutes", 0, True)
    calories = optional_number("calories_burned", 0)
    activity_type = str(data.get("activity_type") or "").strip().lower() or None
    workout_category = str(data.get("workout_category") or "").strip().lower() or None
    workout_name = str(data.get("workout_name") or "").strip() or None
    notes = str(data.get("notes") or "").strip() or None

    if steps is not None and steps > 200000:
        raise ValueError("Steps must not exceed 200000 per record.")
    if distance is not None and distance > 1000:
        raise ValueError("Distance must not exceed 1000 km per record.")
    if duration is not None and duration > 1440:
        raise ValueError("Duration must not exceed 1440 minutes per record.")
    if calories is not None and calories > 10000:
        raise ValueError("Calories burned must not exceed 10000 per record.")
    if notes and len(notes) > 500:
        raise ValueError("Notes must be 500 characters or fewer.")

    if record_type == "daily":
        if steps is None:
            raise ValueError("Steps are required for a daily activity record.")
        activity_type = workout_category = workout_name = None
    elif record_type == "cardio":
        if activity_type not in {"walking", "running", "jogging", "cycling"}:
            raise ValueError("Choose walking, running, jogging, or cycling.")
        if distance is None or distance <= 0:
            raise ValueError("Enter a distance greater than zero.")
        if duration is None or duration <= 0:
            raise ValueError("Enter a duration greater than zero.")
        workout_category = workout_name = None
    else:
        if workout_category not in {"strength_training", "cardio", "calisthenics", "yoga", "other"}:
            raise ValueError("Choose a valid workout category.")
        if not workout_name or len(workout_name) > 120:
            raise ValueError("Workout name is required and must be 120 characters or fewer.")
        if duration is None or duration <= 0:
            raise ValueError("Enter a workout duration greater than zero.")
        activity_type = None

    if record_type != "daily" and steps is not None:
        raise ValueError("Steps can only be entered on a daily activity record.")

    return {
        "record_date": record_date,
        "record_type": record_type,
        "steps": steps,
        "activity_type": activity_type,
        "distance": distance,
        "workout_category": workout_category,
        "workout_name": workout_name,
        "workout_minutes": duration,
        "calories_burned": calories,
        "notes": notes,
    }


def step_goal_value(data):
    raw_goal = number(data, "daily_step_goal", 1)
    if not raw_goal.is_integer():
        raise ValueError("Daily step goal must be a whole number.")
    goal = int(raw_goal)
    if goal > 100000:
        raise ValueError("Daily step goal must not exceed 100000 steps.")
    return goal
