def get_grade_point(percentage: float) -> float:
    """
    Returns the grade point corresponding to the percentage score 
    based on the Narxoz scale.
    """
    if percentage is None:
        return 0.0
    if percentage >= 95.0: return 4.0
    if percentage >= 90.0: return 3.67
    if percentage >= 85.0: return 3.33
    if percentage >= 80.0: return 3.0
    if percentage >= 75.0: return 2.67
    if percentage >= 70.0: return 2.33
    if percentage >= 65.0: return 2.0
    if percentage >= 60.0: return 1.67
    if percentage >= 55.0: return 1.33
    if percentage >= 50.0: return 1.0
    return 0.0

def calculate_gpa(course_scores: dict) -> float:
    """
    Calculates the cumulative GPA based on course scores.
    Expects a dictionary mapping course names to their percentage scores.
    """
    total_points = 0.0
    total_credits = 0

    for course_name, score in course_scores.items():
        credits = 5
        grade_point = 0.0
        
        # Hardcoded rule for Physical Education
        if "Физическая культура" in course_name:
            credits = 2
            grade_point = 4.0
        else:
            grade_point = get_grade_point(score)
            
        total_points += grade_point * credits
        total_credits += credits

    if total_credits == 0:
        return 0.0

    return round(total_points / total_credits, 2)
