import pytest
from src.core.gpa_engine import calculate_gpa, get_grade_point

def test_get_grade_point_boundaries():
    assert get_grade_point(95.0) == 4.0
    assert get_grade_point(94.9) == 3.67
    assert get_grade_point(90.0) == 3.67
    assert get_grade_point(89.9) == 3.33
    assert get_grade_point(85.0) == 3.33
    assert get_grade_point(84.9) == 3.0
    assert get_grade_point(49.9) == 0.0
    
def test_calculate_gpa_all_a():
    # Scenario 1: All 6 subjects at 95% + physical education
    scores = {
        "Философия": 95.0,
        "Kazakh language (B2+)": 96.5,
        "Project management": 100.0,
        "Research Methods": 95.1,
        "HR процессы": 98.0,
        "Цифровой маркетинг": 99.0,
        "Физическая культура": 100.0
    }
    # Expected: All subjects get 4.0, PE gets 4.0. Total GPA should be 4.0
    assert calculate_gpa(scores) == 4.0

def test_calculate_gpa_mixed():
    # Scenario 2: Three subjects at 93% (A-, 3.67), Three subjects at 87% (B+, 3.33), PE (fixed 4.0)
    scores = {
        "Sub1": 93.0,
        "Sub2": 93.0,
        "Sub3": 93.0,
        "Sub4": 87.0,
        "Sub5": 87.0,
        "Sub6": 87.0,
        "Физическая культура - 1": 100.0 # Score shouldn't matter for PE
    }
    
    # Validation manual math:
    # 3.67 * 15 credits = 55.05 points
    # 3.33 * 15 credits = 49.95 points
    # 4.0 * 2 credits (PE) = 8.0 points
    # Total points = 113.0
    # Total credits = 15 + 15 + 2 = 32
    # GPA = 113.0 / 32 = 3.53125 (rounded to 2 decimal places = 3.53)
    
    assert calculate_gpa(scores) == 3.53

def test_calculate_gpa_empty():
    assert calculate_gpa({}) == 0.0

def test_calculate_gpa_no_pe():
    # Just to make sure it works if Physical Education is not in the list
    scores = {
        "Sub1": 95.0, # 4.0 * 5 = 20
        "Sub2": 80.0  # 3.0 * 5 = 15
    }
    # Total points = 35. Total credits = 10. GPA = 3.5
    assert calculate_gpa(scores) == 3.5
