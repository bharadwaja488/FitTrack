BMI_CATEGORIES = (
    (18.5, "Underweight"),
    (25.0, "Healthy weight"),
    (30.0, "Overweight"),
)
ACTIVITY_LEVELS = {
    "sedentary": ("Sedentary", 1.2),
    "light": ("Lightly active", 1.375),
    "moderate": ("Moderately active", 1.55),
    "active": ("Very active", 1.725),
    "very_active": ("Extremely active", 1.9),
}
BMI_EXPLANATION = "BMI is a screening measure, not a direct body-fat measurement or diagnosis."


def _finite_number(value, field):
    from math import isfinite

    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a finite number.")
    if not isfinite(number):
        raise ValueError(f"{field} must be a finite number.")
    return number


def calculate(weight, height_m, age, gender, activity_level):
    """Calculate health metrics at full precision; presentation code rounds for display."""
    return calculate_exact(weight, height_m, age, gender, activity_level)


def calculate_exact(weight, height_m, age, gender, activity_level):
    weight = _finite_number(weight, "Weight")
    height_m = _finite_number(height_m, "Height")
    age_value = _finite_number(age, "Age")
    if not age_value.is_integer() or not 1 <= age_value <= 120:
        raise ValueError("Age must be a whole number between 1 and 120.")
    if not 1 <= weight <= 500:
        raise ValueError("Weight must be between 1 and 500 kg.")
    if not 0 < height_m <= 3:
        raise ValueError("Height must be greater than 0 and at most 3 meters.")
    gender = str(gender or "").strip().lower()
    if gender not in {"male", "female"}:
        raise ValueError("Gender must be male or female.")
    activity_level = str(activity_level or "").strip().lower()
    if activity_level not in ACTIVITY_LEVELS:
        raise ValueError("Choose a valid activity level.")

    activity_label, activity_multiplier = ACTIVITY_LEVELS[activity_level]
    bmi = weight / (height_m * height_m)
    bmi_category = (
        "Underweight" if bmi < BMI_CATEGORIES[0][0]
        else "Healthy weight" if bmi < BMI_CATEGORIES[1][0]
        else "Overweight" if bmi < BMI_CATEGORIES[2][0]
        else "Obesity"
    )
    height_cm = height_m * 100
    bmr = (10 * weight) + (6.25 * height_cm) - (5 * age_value) + (5 if gender == "male" else -161)
    tdee = bmr * activity_multiplier
    return {
        "bmi": bmi,
        "bmi_category": bmi_category,
        "bmi_explanation": BMI_EXPLANATION,
        "bmr": bmr,
        "tdee": tdee,
        "maintenance_calories": tdee,
        "activity_level": activity_level,
        "activity_level_label": activity_label,
        "activity_multiplier": activity_multiplier,
        "bmr_explanation": "Estimated resting energy using the Mifflin–St Jeor equation.",
        "tdee_explanation": "Estimated maintenance calories: BMR multiplied by your activity-level factor.",
    }


def validate_password(value):
    password = str(value or "")
    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must be between 12 and 128 characters.")
    if not any(ch.islower() for ch in password) or not any(ch.isupper() for ch in password) or not any(ch.isdigit() for ch in password):
        raise ValueError("Password must include lowercase and uppercase letters and at least one number.")
    return password
