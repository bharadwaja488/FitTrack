from datetime import date

from ..database import connection
from .health_service import calculate_exact


def activity_metrics(activity_type, distance_km, duration_minutes):
    distance = float(distance_km or 0)
    duration = float(duration_minutes or 0)
    pace = round(duration / distance, 2) if activity_type in {"walking", "running", "jogging"} and distance and duration else None
    speed = round(distance * 60 / duration, 2) if activity_type == "cycling" and distance and duration else None
    return {"average_pace_min_per_km": pace, "average_speed_kmh": speed}


def _present_record(row):
    row["record_date"] = row["record_date"].isoformat()
    row["record_type"] = row["record_type"] or "daily"
    row.update(activity_metrics(row["activity_type"], row["distance"], row["workout_minutes"]))
    return row


def list_records(account_id, start=None, end=None):
    sql = ("SELECT r.record_id,r.record_date,r.steps,r.distance,r.workout_minutes,r.calories_burned,"
           "r.record_type,r.activity_type,r.workout_category,r.workout_name,r.notes "
           "FROM fitness_records r JOIN users u ON u.user_id=r.user_id WHERE u.account_id=%s")
    args = [account_id]
    if start:
        sql += " AND r.record_date >= %s"; args.append(start)
    if end:
        sql += " AND r.record_date <= %s"; args.append(end)
    sql += " ORDER BY r.record_date DESC,r.record_id DESC"
    with connection() as (_, cur):
        cur.execute(sql, tuple(args))
        rows = cur.fetchall()
    return [_present_record(row) for row in rows]


def _record_values(values):
    return tuple(values[key] for key in (
        "record_date", "steps", "distance", "workout_minutes", "calories_burned",
        "record_type", "activity_type", "workout_category", "workout_name", "notes",
    ))


def _record_by_id(account_id, record_id):
    with connection() as (_, cur):
        cur.execute(
            "SELECT r.record_id,r.record_date,r.steps,r.distance,r.workout_minutes,r.calories_burned,"
            "r.record_type,r.activity_type,r.workout_category,r.workout_name,r.notes "
            "FROM fitness_records r JOIN users u ON u.user_id=r.user_id "
            "WHERE u.account_id=%s AND r.record_id=%s",
            (account_id, record_id),
        )
        row = cur.fetchone()
    return _present_record(row) if row else None


def add_record(account_id, values):
    with connection() as (conn, cur):
        cur.execute("SELECT user_id FROM users WHERE account_id=%s FOR UPDATE", (account_id,))
        profile = cur.fetchone()
        if not profile:
            return None
        cur.execute(
            "INSERT INTO fitness_records "
            "(user_id,record_date,steps,distance,workout_minutes,calories_burned,record_type,activity_type,"
            "workout_category,workout_name,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (profile["user_id"], *_record_values(values)),
        )
        record_id = cur.lastrowid
        conn.commit()
    return _record_by_id(account_id, record_id)


def update_record(account_id, record_id, values):
    with connection() as (conn, cur):
        cur.execute(
            "SELECT r.user_id FROM fitness_records r JOIN users u ON u.user_id=r.user_id "
            "WHERE r.record_id=%s AND u.account_id=%s FOR UPDATE",
            (record_id, account_id),
        )
        record = cur.fetchone()
        if not record:
            return None
        cur.execute(
            "UPDATE fitness_records SET record_date=%s,steps=%s,distance=%s,workout_minutes=%s,"
            "calories_burned=%s,record_type=%s,activity_type=%s,workout_category=%s,workout_name=%s,notes=%s "
            "WHERE record_id=%s AND user_id=%s",
            (*_record_values(values), record_id, record["user_id"]),
        )
        conn.commit()
    return _record_by_id(account_id, record_id)


def delete_record(account_id, record_id):
    with connection() as (conn, cur):
        cur.execute(
            "SELECT r.user_id FROM fitness_records r JOIN users u ON u.user_id=r.user_id "
            "WHERE r.record_id=%s AND u.account_id=%s FOR UPDATE",
            (record_id, account_id),
        )
        record = cur.fetchone()
        if not record:
            return False
        cur.execute("DELETE FROM fitness_records WHERE record_id=%s AND user_id=%s", (record_id, record["user_id"]))
        conn.commit()
    return True


def get_step_goal(account_id):
    with connection() as (_, cur):
        cur.execute("SELECT daily_step_goal FROM users WHERE account_id=%s", (account_id,))
        profile = cur.fetchone()
    return int(profile["daily_step_goal"]) if profile and profile["daily_step_goal"] is not None else None


def set_step_goal(account_id, step_goal):
    with connection() as (conn, cur):
        cur.execute("SELECT user_id FROM users WHERE account_id=%s FOR UPDATE", (account_id,))
        if not cur.fetchone():
            return None
        cur.execute("UPDATE users SET daily_step_goal=%s WHERE account_id=%s", (step_goal, account_id))
        conn.commit()
    return step_goal


def dashboard_summary(account_id):
    with connection() as (_, cur):
        cur.execute(
            "SELECT u.weight,u.height,u.age,u.gender,u.activity_level,u.target_calories,u.daily_step_goal,"
            "g.goal_type,g.daily_calorie_target AS goal_daily_calorie_target,g.goal_id "
            "FROM users u LEFT JOIN fitness_goals g ON g.user_id=u.user_id "
            "WHERE u.account_id=%s",
            (account_id,),
        )
        profile = cur.fetchone()
        cur.execute(
            "SELECT COALESCE(SUM(r.steps),0) steps,COALESCE(SUM(r.distance),0) distance,"
            "COALESCE(SUM(r.workout_minutes),0) workout_minutes,"
            "COALESCE(SUM(r.calories_burned),0) calories_burned,COUNT(*) record_count,"
            "COALESCE(SUM(CASE WHEN r.record_date=%s THEN r.steps ELSE 0 END),0) steps_today "
            "FROM fitness_records r JOIN users u ON u.user_id=r.user_id WHERE u.account_id=%s",
            (date.today(), account_id),
        )
        totals = cur.fetchone()

    totals = {
        "steps": int(totals["steps"]),
        "distance": float(totals["distance"]),
        "workout_minutes": int(totals["workout_minutes"]),
        "calories_burned": float(totals["calories_burned"]),
        "record_count": int(totals["record_count"]),
        "steps_today": int(totals["steps_today"]),
    }
    if profile:
        totals.update(calculate_exact(
            profile["weight"], profile["height"], profile["age"], profile["gender"],
            profile["activity_level"],
        ))
        configured_target = profile["goal_daily_calorie_target"]
        if configured_target is None and profile["goal_id"] is None:
            configured_target = profile["target_calories"]
        totals["daily_calorie_target"] = float(configured_target) if configured_target is not None else None
        totals["goal"] = profile["goal_type"]
        step_goal = profile["daily_step_goal"]
        totals["daily_step_goal"] = int(step_goal) if step_goal is not None else None
        totals["steps_remaining"] = max(int(step_goal) - totals["steps_today"], 0) if step_goal is not None else None
        totals["step_goal_percentage"] = round(totals["steps_today"] / int(step_goal) * 100, 1) if step_goal else None
    else:
        totals.update({
            "bmi": None,
            "bmi_category": None,
            "bmi_explanation": None,
            "bmr": None,
            "tdee": None,
            "maintenance_calories": None,
            "activity_level": None,
            "activity_level_label": None,
            "activity_multiplier": None,
            "bmr_explanation": None,
            "tdee_explanation": None,
            "daily_calorie_target": None,
            "goal": None,
            "steps_today": 0,
            "daily_step_goal": None,
            "steps_remaining": None,
            "step_goal_percentage": None,
        })
    return totals


def dashboard_activity(account_id, period="week"):
    interval = {"week": 6, "month": 29}.get(period)
    if interval is None:
        raise ValueError("Period must be week or month.")
    with connection() as (_, cur):
        cur.execute(
            "SELECT r.record_date,COALESCE(SUM(r.steps),0) steps,"
            "COALESCE(SUM(CASE WHEN r.record_type='cardio' OR r.record_type IS NULL THEN r.distance ELSE 0 END),0) cardio_distance_km,"
            "COALESCE(SUM(r.workout_minutes),0) workout_minutes,"
            "COALESCE(SUM(r.calories_burned),0) calories_burned,"
            "SUM(CASE WHEN r.record_type='workout' THEN 1 ELSE 0 END) workout_count "
            "FROM fitness_records r JOIN users u ON u.user_id=r.user_id "
            "WHERE u.account_id=%s AND r.record_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
            "GROUP BY r.record_date ORDER BY r.record_date",
            (account_id, interval),
        )
        rows = cur.fetchall()
    for row in rows:
        row["record_date"] = row["record_date"].isoformat()
        for key in ("steps", "workout_minutes", "workout_count"):
            row[key] = int(row[key] or 0)
        for key in ("cardio_distance_km", "calories_burned"):
            row[key] = float(row[key] or 0)
    return rows
