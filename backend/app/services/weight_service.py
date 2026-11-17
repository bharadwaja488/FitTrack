from datetime import date, datetime, time, timezone
from math import isfinite

from ..database import connection
from .goal_service import goal_reached
from .health_service import calculate_exact
from .progress_service import weight_trend


def parse_recorded_at(value=None):
    if value in (None, ""):
        return datetime.now()
    text = str(value).strip()
    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            parsed = datetime.combine(parsed_date, time(hour=12))
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Recorded date must be an ISO date or datetime.")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    if parsed.date() > datetime.now().date():
        raise ValueError("Weight records cannot be dated in the future.")
    return parsed


def validate_weight(value):
    if isinstance(value, bool):
        raise ValueError("Weight must be a finite number.")
    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise ValueError("Weight must be a finite number.")
    if not isfinite(weight) or not 1 <= weight <= 500:
        raise ValueError("Weight must be between 1 and 500 kg.")
    return weight


def list_weight_records(account_id, start=None, end=None):
    sql = (
        "SELECT wr.record_id,wr.weight_kg,wr.recorded_at FROM weight_records wr "
        "JOIN users u ON u.user_id=wr.user_id WHERE u.account_id=%s"
    )
    args = [account_id]
    if start:
        sql += " AND wr.recorded_at >= %s"
        args.append(start)
    if end:
        sql += " AND wr.recorded_at < %s"
        args.append(end)
    sql += " ORDER BY wr.recorded_at DESC,wr.record_id DESC"
    with connection() as (_, cur):
        cur.execute(sql, tuple(args))
        rows = cur.fetchall()
    for row in rows:
        row["weight_kg"] = float(row["weight_kg"])
        row["recorded_at"] = row["recorded_at"].isoformat(sep=" ")
    return rows


def weight_overview(account_id, start=None, end=None):
    rows = list_weight_records(account_id, start, end)
    progress_rows = [
        {"weight_kg": row["weight_kg"], "recorded_at": datetime.fromisoformat(row["recorded_at"])}
        for row in rows
    ]
    with connection() as (_, cur):
        cur.execute("SELECT weight FROM users WHERE account_id=%s", (account_id,))
        profile = cur.fetchone()
    return {
        "records": rows,
        "trend": weight_trend(progress_rows),
        "current_weight_kg": float(profile["weight"]) if profile else None,
    }


def add_weight_record(account_id, weight, recorded_at):
    weight = validate_weight(weight)
    recorded_at = parse_recorded_at(recorded_at)
    with connection() as (conn, cur):
        profile = _lock_profile(cur, account_id)
        if not profile:
            return None
        cur.execute(
            "INSERT INTO weight_records (user_id,weight_kg,recorded_at) VALUES (%s,%s,%s)",
            (profile["user_id"], weight, recorded_at),
        )
        record_id = cur.lastrowid
        _sync_profile_to_latest_weight(cur, profile["user_id"])
        conn.commit()
    return next(row for row in list_weight_records(account_id) if row["record_id"] == record_id)


def update_weight_record(account_id, record_id, weight, recorded_at):
    weight = validate_weight(weight)
    recorded_at = parse_recorded_at(recorded_at)
    with connection() as (conn, cur):
        cur.execute(
            "SELECT wr.user_id FROM weight_records wr JOIN users u ON u.user_id=wr.user_id "
            "WHERE wr.record_id=%s AND u.account_id=%s FOR UPDATE",
            (record_id, account_id),
        )
        owned = cur.fetchone()
        if not owned:
            return False
        cur.execute(
            "UPDATE weight_records SET weight_kg=%s,recorded_at=%s WHERE record_id=%s",
            (weight, recorded_at, record_id),
        )
        _sync_profile_to_latest_weight(cur, owned["user_id"])
        conn.commit()
    return next(row for row in list_weight_records(account_id) if row["record_id"] == record_id)


def delete_weight_record(account_id, record_id):
    with connection() as (conn, cur):
        cur.execute(
            "SELECT wr.user_id FROM weight_records wr JOIN users u ON u.user_id=wr.user_id "
            "WHERE wr.record_id=%s AND u.account_id=%s FOR UPDATE",
            (record_id, account_id),
        )
        owned = cur.fetchone()
        if not owned:
            return False
        cur.execute("DELETE FROM weight_records WHERE record_id=%s", (record_id,))
        _sync_profile_to_latest_weight(cur, owned["user_id"])
        conn.commit()
    return True


def _lock_profile(cur, account_id):
    cur.execute(
        "SELECT user_id,weight,height,age,gender,activity_level FROM users "
        "WHERE account_id=%s FOR UPDATE",
        (account_id,),
    )
    return cur.fetchone()


def _sync_profile_to_latest_weight(cur, user_id):
    cur.execute(
        "SELECT weight_kg FROM weight_records WHERE user_id=%s "
        "ORDER BY recorded_at DESC,record_id DESC LIMIT 1",
        (user_id,),
    )
    latest = cur.fetchone()
    if not latest:
        return
    weight = float(latest["weight_kg"])
    cur.execute(
        "SELECT height,age,gender,activity_level FROM users WHERE user_id=%s",
        (user_id,),
    )
    profile = cur.fetchone()
    health = calculate_exact(weight, profile["height"], profile["age"], profile["gender"], profile["activity_level"])
    cur.execute("UPDATE users SET weight=%s,bmi=%s WHERE user_id=%s", (weight, health["bmi"], user_id))
    cur.execute(
        "SELECT goal_type,target_weight_kg,status FROM fitness_goals WHERE user_id=%s FOR UPDATE",
        (user_id,),
    )
    goal = cur.fetchone()
    if goal and goal["status"] == "active" and goal_reached(
        goal["goal_type"], weight, float(goal["target_weight_kg"]),
    ):
        cur.execute("UPDATE fitness_goals SET status='completed' WHERE user_id=%s", (user_id,))
