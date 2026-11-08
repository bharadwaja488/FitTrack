import pytest
from fittrack_core import bmi_category, calculate_bmi, calculate_bmr, calculate_daily_calories

def test_bmi():
    assert calculate_bmi(70, 1.75) == pytest.approx(22.8571, rel=1e-4)

def test_bmi_rejects_zero_height():
    with pytest.raises(ValueError):
        calculate_bmi(70, 0)

def test_bmr_male():
    assert calculate_bmr(25, 'male', 70, 1.75) == pytest.approx(1673.75)

def test_bmr_female():
    assert calculate_bmr(25, 'female', 60, 1.65) == pytest.approx(1345.25)

def test_bmr_rejects_unknown_gender():
    with pytest.raises(ValueError):
        calculate_bmr(25, 'other', 70, 1.75)

def test_activity_factor():
    assert calculate_daily_calories(2000, 'Moderate (3-5 days/week)') == pytest.approx(3100)

def test_bmi_category():
    assert bmi_category(22) == 'Within the adult reference range'