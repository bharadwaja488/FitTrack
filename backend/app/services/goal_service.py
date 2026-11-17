from math import isfinite

from ..database import connection
from .health_service import calculate_exact
from .progress_service import goal_progress, weight_trend


GOALS = {"weight_loss", "maintenance", "weight_gain", "muscle_building"}
GOAL_LABELS = {
    "weight_loss": "Weight loss",
    "maintenance": "Maintenance",
    "weight_gain": "Weight gain",
    "muscle_building": "Muscle building",
}
GOAL_STATUSES = {"active", "paused", "completed", "cancelled"}
DEFAULT_ADJUSTMENTS = {"weight_loss": 300.0, "weight_gain": 200.0, "muscle_building": 200.0}


def calorie_suggestion(tdee, goal_type, adjustment=None):
    if goal_type not in GOALS:
        raise ValueError("Choose a supported fitness goal.")
    if goal_type == "maintenance":
        adjustment = 0.0
        target = float(tdee)
    else:
        if adjustment is None:
            adjustment = DEFAULT_ADJUSTMENTS[goal_type]
        if isinstance(adjustment, bool):
            raise ValueError("Calorie adjustment must be a number.")
        try:
            adjustment = float(adjustment)
        except (TypeError, ValueError):
            raise ValueError("Calorie adjustment must be a number.")
        upper = 500 if goal_type == "weight_loss" else 300
        if not isfinite(adjustment) or not 100 <= adjustment <= upper:
            raise ValueError(f"Choose a conservative adjustment from 100 to {upper} kcal/day.")
        target = float(tdee) + (-adjustment if goal_type == "weight_loss" else adjustment)
    if not isfinite(target) or target <= 0:
        raise ValueError("The estimated calorie target must be positive.")
    return {"calorie_adjustment": adjustment, "suggested_target": target}


def goal_reached(goal_type, current_weight, target_weight):
    if goal_type == "weight_loss":
        return current_weight <= target_weight
    if goal_type in {"weight_gain", "muscle_building"}:
        return current_weight >= target_weight
    return False


def create_or_update_goal(account_id, data):
    goal_type = str(data.get("goal_type", "")).strip().lower()
    if goal_type not in GOALS:
        raise ValueError("Choose a supported fitness goal.")
    confirm_target = data.get("confirm_calorie_target", False)
    if not isinstance(confirm_target, bool):
        raise ValueError("Confirm the calorie estimate with a true or false value.")

    with connection() as (conn, cur):
        cur.execute(
            "SELECT user_id,weight,height,age,gender,activity_level FROM users "
            "WHERE account_id=%s FOR UPDATE",
            (account_id,),
        )
        profile = cur.fetchone()
        if not profile:
            return None

        start_weight = float(profile["weight"])
        target_input = data.get("target_weight_kg")
        if target_input in (None, "") and goal_type == "maintenance":
            target_weight = start_weight
        else:
            target_weight = _weight(target_input, "Target weight")
        if not 1 <= target_weight <= 500:
            raise ValueError("Target weight must be between 1 and 500 kg.")
        if goal_type == "maintenance" and round(target_weight, 2) != round(start_weight, 2):
            raise ValueError("A maintenance target must match your starting weight.")
        if goal_type == "weight_loss" and target_weight >= start_weight:
            raise ValueError("A weight-loss target must be below your starting weight.")
        if goal_type in {"weight_gain", "muscle_building"} and target_weight <= start_weight:
            raise ValueError("A gain or muscle-building target must be above your starting weight.")

        health = calculate_exact(
            profile["weight"], profile["height"], profile["age"], profile["gender"],
            profile["activity_level"],
        )
        estimate = calorie_suggestion(health["tdee"], goal_type, data.get("calorie_adjustment"))
        confirmed_target = estimate["suggested_target"] if confirm_target else None
        cur.execute(
            "INSERT INTO fitness_goals "
            "(user_id,goal_type,starting_weight_kg,target_weight_kg,created_at,status,"
            "calorie_adjustment,daily_calorie_target) "
            "VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP,'active',%s,%s) "
            "ON DUPLICATE KEY UPDATE goal_type=VALUES(goal_type),"
            "starting_weight_kg=VALUES(starting_weight_kg),target_weight_kg=VALUES(target_weight_kg),"
            "created_at=VALUES(created_at),status='active',"
            "calorie_adjustment=VALUES(calorie_adjustment),"
            "daily_calorie_target=VALUES(daily_calorie_target)",
            (profile["user_id"], goal_type, start_weight, target_weight,
             estimate["calorie_adjustment"], confirmed_target),
        )
        conn.commit()
    return get_goal(account_id)


def get_goal(account_id):
    with connection() as (_, cur):
        cur.execute(
            "SELECT u.user_id,u.weight,u.height,u.age,u.gender,u.activity_level,"
            "g.goal_id,g.goal_type,g.starting_weight_kg,g.target_weight_kg,g.created_at,"
            "g.status,g.calorie_adjustment,g.daily_calorie_target "
            "FROM users u LEFT JOIN fitness_goals g ON g.user_id=u.user_id "
            "WHERE u.account_id=%s",
            (account_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"goal": None, "progress": None, "current_weight_kg": None}
        cur.execute(
            "SELECT record_id,weight_kg,recorded_at FROM weight_records "
            "WHERE user_id=%s ORDER BY recorded_at,record_id",
            (row["user_id"],),
        )
        records = cur.fetchall()

    health = calculate_exact(row["weight"], row["height"], row["age"], row["gender"], row["activity_level"])
    records_for_progress = [
        {"weight_kg": float(record["weight_kg"]), "recorded_at": record["recorded_at"]}
        for record in records
    ]
    if row["goal_id"] is None:
        return {
            "goal": None,
            "progress": weight_trend(records_for_progress),
            "current_weight_kg": float(row["weight"]),
        }

    goal_type = row["goal_type"]
    adjustment = row["calorie_adjustment"]
    suggestion = calorie_suggestion(health["tdee"], goal_type, adjustment if goal_type != "maintenance" else 0)
    goal = {
        "goal_id": row["goal_id"],
        "goal_type": goal_type,
        "goal_label": GOAL_LABELS[goal_type],
        "starting_weight_kg": float(row["starting_weight_kg"]),
        "target_weight_kg": float(row["target_weight_kg"]),
        "created_at": row["created_at"].isoformat(sep=" "),
        "status": row["status"],
        "calorie_adjustment": suggestion["calorie_adjustment"],
        "suggested_calorie_target": suggestion["suggested_target"],
        "daily_calorie_target": (
            float(row["daily_calorie_target"])
            if row["daily_calorie_target"] is not None else None
        ),
        "tdee": health["tdee"],
        "activity_level_label": health["activity_level_label"],
        "calorie_estimate_note": "Estimated daily intake, not a medical prescription.",
    }
    return {
        "goal": goal,
        "progress": goal_progress(goal, row["weight"], records_for_progress),
        "current_weight_kg": float(row["weight"]),
    }


def update_goal_status(account_id, status):
    status = str(status or "").strip().lower()
    if status not in {"active", "paused", "cancelled"}:
        raise ValueError("Choose active, paused, or cancelled status.")
    with connection() as (conn, cur):
        cur.execute(
            "SELECT g.status FROM fitness_goals g JOIN users u ON u.user_id=g.user_id "
            "WHERE u.account_id=%s FOR UPDATE",
            (account_id,),
        )
        existing = cur.fetchone()
        if not existing:
            return None
        if existing["status"] == "completed":
            raise ValueError("A completed goal cannot be reactivated.")
        cur.execute(
            "UPDATE fitness_goals g JOIN users u ON u.user_id=g.user_id "
            "SET g.status=%s WHERE u.account_id=%s",
            (status, account_id),
        )
        conn.commit()
    return get_goal(account_id)


def _weight(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a finite number.")
    if not isfinite(number):
        raise ValueError(f"{field} must be a finite number.")
    return number
