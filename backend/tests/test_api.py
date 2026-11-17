import sys
import math

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.services.health_service import calculate, calculate_exact, validate_password
from app.utils.validators import profile_values


@pytest.mark.parametrize("age", [20.5, "20.5", float("inf"), True])
def test_profile_age_must_be_a_finite_whole_number(age):
    with pytest.raises(ValueError):
        profile_values({"full_name": "Test User", "gender": "male", "activity_level": "moderate",
                        "age": age, "height": 1.75, "weight": 70})


def test_profile_age_accepts_whole_number_values():
    values = profile_values({"full_name": "Test User", "gender": "male", "activity_level": "moderate",
                             "age": "20", "height": 1.75, "weight": 70})
    assert values[1] == 20


def test_health_calculations_match_mifflin_st_jeor_and_reference_profile():
    male = calculate(70, 1.75, 30, "male", "moderate")
    female = calculate(70, 1.75, 30, "female", "moderate")
    assert male["bmi"] == pytest.approx(70 / 1.75**2)
    assert male["bmr"] == pytest.approx(1648.75)
    assert male["tdee"] == pytest.approx(1648.75 * 1.55)
    assert female["bmr"] == pytest.approx(1482.75)
    assert female["tdee"] == pytest.approx(1482.75 * 1.55)

    reference = calculate_exact(92, 1.753, 20, "male", "moderate")
    assert reference["bmi"] == pytest.approx(29.94, abs=0.01)
    assert reference["bmr"] == pytest.approx(1920.625)
    assert reference["tdee"] == pytest.approx(2976.96875)
    assert reference["maintenance_calories"] == reference["tdee"]
    assert "direct body-fat measurement" in reference["bmi_explanation"]


def test_onboarding_e2e_profile_calculations_match_dashboard_display_case():
    result = calculate_exact(62, 1.66, 31, "female", "moderate")
    assert result["bmi"] == pytest.approx(22.4996371)
    assert result["bmi_category"] == "Healthy weight"
    assert result["bmr"] == pytest.approx(1341.5)
    assert result["tdee"] == pytest.approx(2079.325)
    assert result["activity_multiplier"] == 1.55


@pytest.mark.parametrize("level,multiplier", [
    ("sedentary", 1.2),
    ("light", 1.375),
    ("moderate", 1.55),
    ("active", 1.725),
    ("very_active", 1.9),
])
def test_activity_multiplier_is_applied(level, multiplier):
    result = calculate_exact(82.5, 1.68, 46, "female", level)
    assert result["activity_multiplier"] == multiplier
    assert result["tdee"] == pytest.approx(result["bmr"] * multiplier)
    assert result["activity_level"] == level


@pytest.mark.parametrize("bmi,category", [
    (18.49, "Underweight"),
    (18.5, "Healthy weight"),
    (24.9, "Healthy weight"),
    (25.0, "Overweight"),
    (29.9, "Overweight"),
    (30.0, "Obesity"),
])
def test_bmi_category_thresholds(bmi, category):
    result = calculate_exact(bmi, 1.0, 25, "male", "sedentary")
    assert result["bmi"] == pytest.approx(bmi)
    assert result["bmi_category"] == category


@pytest.mark.parametrize("weight,height,age,gender,activity", [
    (None, 1.75, 20, "male", "moderate"),
    (70, None, 20, "male", "moderate"),
    (70, 1.75, None, "male", "moderate"),
    (70, 1.75, 20, "other", "moderate"),
    (70, 1.75, 20, "male", "missing"),
    (float("inf"), 1.75, 20, "male", "moderate"),
    (0, 1.75, 20, "male", "moderate"),
    (70, 0, 20, "male", "moderate"),
    (70, 1.75, 20.5, "male", "moderate"),
])
def test_invalid_health_inputs_are_rejected(weight, height, age, gender, activity):
    with pytest.raises(ValueError):
        calculate(weight, height, age, gender, activity)


def test_calculations_keep_full_precision_until_display():
    result = calculate(92, 1.753, 20, "male", "moderate")
    assert math.isclose(result["bmi"], 92 / (1.753 * 1.753), rel_tol=0, abs_tol=1e-12)
    assert math.isclose(result["bmr"], 1920.625, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(result["tdee"], 2976.96875, rel_tol=0, abs_tol=1e-12)


def test_password_strength_validation():
    assert validate_password("FitTrackSecure2026") == "FitTrackSecure2026"
    try:
        validate_password("weak")
    except ValueError as error:
        assert "12 and 128" in str(error)
    else:
        raise AssertionError("Weak password must be rejected")


def test_private_routes_require_an_authenticated_session():
    client = create_app().test_client()
    for endpoint in ("/api/auth/me", "/api/profile", "/api/fitness", "/api/fitness/history",
                     "/api/dashboard/summary", "/api/dashboard/activity"):
        response = client.get(endpoint)
        assert response.status_code == 401, endpoint


def test_mutations_require_csrf_token():
    client = create_app().test_client()
    response = client.post("/api/auth/login", json={"email": "x@example.com", "password": "x"})
    assert response.status_code == 400
    assert response.json["error"]["code"] == "csrf_failed"


def test_csrf_bootstrap_and_google_provider_discovery():
    app = create_app()
    app.config["GOOGLE_ENABLED"] = False
    client = app.test_client()
    csrf = client.get("/api/auth/csrf")
    assert csrf.status_code == 200
    assert len(csrf.json["data"]["csrf_token"]) >= 32
    providers = client.get("/api/auth/providers")
    assert providers.status_code == 200
    assert providers.json["data"]["google_enabled"] is False
    assert client.get("/api/auth/google").status_code == 503


def test_password_reset_is_neutral_when_mail_is_not_configured():
    app = create_app()
    app.config["MAIL_ENABLED"] = False
    client = app.test_client()
    token = client.get("/api/auth/csrf").json["data"]["csrf_token"]
    response = client.post("/api/auth/forgot-password", json={"email": "person@example.com"},
                           headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    assert response.json["data"]["mail_configured"] is False
