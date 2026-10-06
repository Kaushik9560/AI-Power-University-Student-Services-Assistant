"""Deterministic tools."""
import pytest

from app.tools import student_tools as T


def test_attendance_percentage_is_pure():
    assert T.calculate_attendance_percentage(41, 50) == 82.0
    assert T.calculate_attendance_percentage(40, 50) == 80.0
    with pytest.raises(T.ToolError):
        T.calculate_attendance_percentage(1, 0)


def test_course_resolution():
    assert T.find_course_in_text("What is my attendance in DBMS?", "S1001")["course_code"] == "CS301"
    assert T.find_course_in_text("my result in Data Structures", "S1001")["course_code"] == "CS201"
    assert T.find_course_in_text("attendance in cs302", "S1001")["course_code"] == "CS302"
    assert T.find_course_in_text("Mathematics result", "S1001")["course_code"] == "MA201"
    assert T.find_course_in_text("Mathematics result", "S1017")["course_code"] == "EC202"  # ECE student → own course
    assert T.find_course_in_text("my CGPA", "S1001") is None


def test_backlogs_derived_from_results():
    b = T.get_active_backlogs("S1009")
    assert b["count"] == 3 and b["stored_active_backlogs"] == 3
    assert T.get_active_backlogs("S1011")["count"] == 0  # cleared in supplementary


def test_missing_record_raises():
    with pytest.raises(T.ToolError):
        T.get_attendance("S1001", "EC401")
