from ..database import connection
from .goal_service import goal_reached
from .health_service import calculate_exact


def _health_values(profile):
    values = calculate_exact(
        profile["weight"], profile["height"], profile["age"], profile["gender"],
        profile["activity_level"],
    )
    configured_target = profile.get("goal_daily_calorie_target")
    if configured_target is None and profile.get("goal_id") is None:
        configured_target = profile.get("target_calories")
    values["daily_calorie_target"] = float(configured_target) if configured_target is not None else None
    values["goal"] = profile.get("goal_type")
    return values


def get_profile(account_id):
    with connection() as (_, cur):
        cur.execute(
            "SELECT u.name,u.age,u.gender,u.height,u.weight,u.activity_level,u.goal,u.target_calories,"
            "g.goal_id,g.goal_type,g.daily_calorie_target AS goal_daily_calorie_target "
            "FROM users u LEFT JOIN fitness_goals g ON g.user_id=u.user_id "
            "WHERE u.account_id=%s",
            (account_id,),
        )
        profile = cur.fetchone()
    if profile:
        profile.update(_health_values(profile))
    return profile


def save_profile(account_id, values):
    full_name, age, gender, height, weight, activity_level = values
    health = calculate_exact(weight, height, age, gender, activity_level)
    with connection() as (conn, cur):
        cur.execute("SELECT user_id FROM users WHERE account_id=%s FOR UPDATE", (account_id,))
        current = cur.fetchone()
        if current:
            cur.execute(
                "UPDATE users SET name=%s,age=%s,gender=%s,height=%s,weight=%s,bmi=%s,"
                "activity_level=%s WHERE account_id=%s",
                (full_name, age, gender, height, weight, health["bmi"], activity_level, account_id),
            )
        else:
            cur.execute(
                "INSERT INTO users (account_id,name,age,gender,height,weight,bmi,activity_level) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (account_id, full_name, age, gender, height, weight, health["bmi"], activity_level),
            )
        cur.execute("UPDATE accounts SET full_name=%s WHERE account_id=%s", (full_name, account_id))
        cur.execute(
            "SELECT g.user_id,g.goal_type,g.target_weight_kg,g.status FROM fitness_goals g "
            "JOIN users u ON u.user_id=g.user_id WHERE u.account_id=%s FOR UPDATE",
            (account_id,),
        )
        goal = cur.fetchone()
        if goal and goal["status"] == "active" and goal_reached(
            goal["goal_type"], float(weight), float(goal["target_weight_kg"]),
        ):
            cur.execute("UPDATE fitness_goals SET status='completed' WHERE user_id=%s", (goal["user_id"],))
        conn.commit()
    return get_profile(account_id)
