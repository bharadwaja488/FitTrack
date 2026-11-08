"""Core calculations and MySQL persistence for FitTrack's dashboard."""
from __future__ import annotations
from datetime import date
from typing import Any

ACTIVITY_FACTORS = {
    "Sedentary (little or no exercise)": 1.20,
    "Light (1-3 days/week)": 1.375,
    "Moderate (3-5 days/week)": 1.55,
    "Very active (6-7 days/week)": 1.725,
    "Extra active (physical job + training)": 1.90,
}

def calculate_bmi(weight_kg: float, height_m: float) -> float:
    if weight_kg <= 0 or height_m <= 0:
        raise ValueError("Weight and height must be positive numbers.")
    return weight_kg / (height_m ** 2)

def calculate_bmr(age: int, gender: str, weight_kg: float, height_m: float) -> float:
    """Mifflin-St Jeor estimate; gender must be male or female."""
    if age <= 0 or weight_kg <= 0 or height_m <= 0:
        raise ValueError("Age, weight and height must be positive numbers.")
    sex = gender.strip().lower()
    if sex not in {"male", "female"}:
        raise ValueError("For this BMR equation, gender must be 'male' or 'female'.")
    offset = 5 if sex == "male" else -161
    return (10 * weight_kg) + (6.25 * height_m * 100) - (5 * age) + offset

def calculate_daily_calories(bmr: float, activity_level: str) -> float:
    factor = ACTIVITY_FACTORS.get(activity_level)
    if factor is None:
        raise ValueError("Choose a valid activity level.")
    return bmr * factor

def bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "Below the adult reference range"
    if bmi < 25:
        return "Within the adult reference range"
    if bmi < 30:
        return "Above the adult reference range"
    return "High adult BMI range"

def _execute(sql: str, params: tuple[Any, ...] = (), fetch: str | None = None):
    from database import create_connection
    connection = create_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, params)
        result = cursor.fetchall() if fetch == "all" else cursor.fetchone() if fetch == "one" else cursor.lastrowid
        if fetch is None:
            connection.commit()
        return result
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

def ensure_upgrade_tables() -> None:
    """Additive migration: preserve the original users and fitness_records tables."""
    from database import create_connection
    statements = [
        """CREATE TABLE IF NOT EXISTS daily_health_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
            log_date DATE NOT NULL, water_ml INT NOT NULL DEFAULT 0,
            sleep_hours DECIMAL(4,2) NOT NULL DEFAULT 0, mood VARCHAR(30) NULL,
            notes TEXT NULL, UNIQUE KEY uq_health_user_date (user_id, log_date),
            CONSTRAINT fk_health_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS weight_history (
            weight_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
            log_date DATE NOT NULL, weight_kg DECIMAL(6,2) NOT NULL,
            UNIQUE KEY uq_weight_user_date (user_id, log_date),
            CONSTRAINT fk_weight_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS fitness_goals (
            goal_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,
            goal_type VARCHAR(40) NOT NULL, target_value DECIMAL(10,2) NOT NULL,
            target_date DATE NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_goal_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB""",
    ]
    connection = create_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

def get_users() -> list[dict[str, Any]]:
    return _execute(
        "SELECT user_id, name, age, gender, height, weight, bmi, daily_calories FROM users ORDER BY user_id DESC",
        fetch="all",
    ) or []

def create_user(name: str, age: int, gender: str, height_m: float, weight_kg: float) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Name cannot be empty.")
    bmi = calculate_bmi(weight_kg, height_m)
    bmr = calculate_bmr(age, gender, weight_kg, height_m)
    calories = calculate_daily_calories(bmr, "Sedentary (little or no exercise)")
    return _execute(
        """INSERT INTO users (name, age, gender, height, weight, bmi, daily_calories)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (name, age, gender, height_m, weight_kg, bmi, calories),
    )

def add_fitness_record(user_id: int, record_date: date, steps: int, distance_km: float,
                       workout_minutes: int, calories_burned: float) -> None:
    if min(steps, distance_km, workout_minutes, calories_burned) < 0:
        raise ValueError("Activity values cannot be negative.")
    _execute(
        """INSERT INTO fitness_records
           (user_id, record_date, steps, distance, workout_minutes, calories_burned)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, record_date, steps, distance_km, workout_minutes, calories_burned),
    )

def get_fitness_records(user_id: int, limit: int = 365) -> list[dict[str, Any]]:
    return _execute(
        """SELECT record_id, user_id, record_date, steps, distance, workout_minutes, calories_burned
           FROM fitness_records WHERE user_id = %s ORDER BY record_date DESC, record_id DESC LIMIT %s""",
        (user_id, limit), fetch="all",
    ) or []

def save_health_log(user_id: int, log_date: date, water_ml: int, sleep_hours: float,
                    mood: str, notes: str) -> None:
    if water_ml < 0 or not 0 <= sleep_hours <= 24:
        raise ValueError("Water must be non-negative and sleep must be between 0 and 24 hours.")
    _execute(
        """INSERT INTO daily_health_logs (user_id, log_date, water_ml, sleep_hours, mood, notes)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE water_ml=VALUES(water_ml), sleep_hours=VALUES(sleep_hours),
             mood=VALUES(mood), notes=VALUES(notes)""",
        (user_id, log_date, water_ml, sleep_hours, mood or None, notes or None),
    )

def get_health_logs(user_id: int, limit: int = 90) -> list[dict[str, Any]]:
    return _execute(
        """SELECT log_date, water_ml, sleep_hours, mood, notes FROM daily_health_logs
           WHERE user_id=%s ORDER BY log_date DESC LIMIT %s""",
        (user_id, limit), fetch="all",
    ) or []

def save_weight(user_id: int, log_date: date, weight_kg: float) -> None:
    if weight_kg <= 0:
        raise ValueError("Weight must be greater than zero.")
    _execute(
        """INSERT INTO weight_history (user_id, log_date, weight_kg) VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE weight_kg=VALUES(weight_kg)""",
        (user_id, log_date, weight_kg),
    )

def get_weight_history(user_id: int, limit: int = 180) -> list[dict[str, Any]]:
    return _execute(
        """SELECT log_date, weight_kg FROM weight_history
           WHERE user_id=%s ORDER BY log_date DESC LIMIT %s""",
        (user_id, limit), fetch="all",
    ) or []

def create_goal(user_id: int, goal_type: str, target_value: float, target_date: date) -> int:
    if target_value <= 0:
        raise ValueError("Goal target must be greater than zero.")
    return _execute(
        "INSERT INTO fitness_goals (user_id, goal_type, target_value, target_date) VALUES (%s, %s, %s, %s)",
        (user_id, goal_type, target_value, target_date),
    )

def get_goals(user_id: int) -> list[dict[str, Any]]:
    return _execute(
        """SELECT goal_id, goal_type, target_value, target_date, status, created_at
           FROM fitness_goals WHERE user_id=%s ORDER BY created_at DESC""",
        (user_id,), fetch="all",
    ) or []

def update_goal_status(goal_id: int, status: str) -> None:
    if status not in {"active", "completed", "paused"}:
        raise ValueError("Invalid goal status.")
    _execute("UPDATE fitness_goals SET status=%s WHERE goal_id=%s", (status, goal_id))
