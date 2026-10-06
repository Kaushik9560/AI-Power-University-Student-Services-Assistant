import sqlite3
import re
from typing import Optional, List, Dict, Any
from app.db.database import get_connection

class ToolError(Exception):
    """Raised when a required database record is missing or input is unresolvable."""
    pass

def calculate_attendance_percentage(classes_attended: int, classes_held: int) -> float:
    """The single point in the entire application where attendance percentage is calculated."""
    if classes_held <= 0:
        raise ToolError("Classes held must be strictly greater than zero.")
    return round((classes_attended / classes_held) * 100.0, 2)

def get_student(student_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ToolError(f"Student with ID '{student_id}' does not exist.")
    return dict(row)

def get_course(course_code: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM courses WHERE course_code = ?", (course_code.upper(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ToolError(f"Course '{course_code}' does not exist.")
    return dict(row)

def find_course_in_text(text: str, db_path: Optional[str] = None) -> str:
    """Resolves course code or informal terms (e.g. 'DBMS' -> 'CS301')."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT course_code, course_name FROM courses")
    courses = cursor.fetchall()
    conn.close()
    
    text_clean = text.upper()
    for row in courses:
        code = row["course_code"].upper()
        name = row["course_name"].upper()
        if re.search(r'\b' + re.escape(code) + r'\b', text_clean):
            return code
        
        # Check acronyms (e.g. Database Management Systems -> DBMS)
        words = re.findall(r'\b[A-Z]', name)
        acronym = "".join(words)
        if len(acronym) > 1 and re.search(r'\b' + re.escape(acronym) + r'\b', text_clean):
            return row["course_code"]
            
        if name in text_clean:
            return row["course_code"]

    raise ToolError(f"Could not identify any valid course from input text: '{text}'.")

def get_attendance(student_id: str, course_code: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT classes_held, classes_attended FROM attendance WHERE student_id = ? AND course_code = ?",
        (student_id, course_code.upper())
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ToolError(f"No attendance record for student '{student_id}' in course '{course_code}'.")
    
    held = row["classes_held"]
    attended = row["classes_attended"]
    pct = calculate_attendance_percentage(attended, held)
    return {
        "student_id": student_id,
        "course_code": course_code.upper(),
        "classes_held": held,
        "classes_attended": attended,
        "attendance_percentage": pct
    }

def get_aggregate_attendance(student_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT SUM(classes_held) as total_held, SUM(classes_attended) as total_attended "
        "FROM attendance WHERE student_id = ?",
        (student_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row or row["total_held"] is None or row["total_held"] == 0:
        raise ToolError(f"No aggregate attendance records found for student '{student_id}'.")
    
    held = row["total_held"]
    attended = row["total_attended"]
    pct = calculate_attendance_percentage(attended, held)
    return {
        "student_id": student_id,
        "total_classes_held": held,
        "total_classes_attended": attended,
        "aggregate_percentage": pct
    }

def get_result(student_id: str, course_code: str, exam_session: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    if exam_session:
        cursor.execute(
            "SELECT * FROM results WHERE student_id = ? AND course_code = ? AND exam_session = ?",
            (student_id, course_code.upper(), exam_session)
        )
    else:
        cursor.execute(
            "SELECT * FROM results WHERE student_id = ? AND course_code = ? ORDER BY exam_session DESC LIMIT 1",
            (student_id, course_code.upper())
        )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ToolError(f"No exam results found for student '{student_id}' in '{course_code}'.")
    return dict(row)

def get_active_backlogs(student_id: str, db_path: Optional[str] = None) -> int:
    """Calculates active backlogs directly from results history."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT course_code, result, exam_session FROM results WHERE student_id = ? ORDER BY exam_session ASC",
        (student_id,)
    )
    records = cursor.fetchall()
    conn.close()
    
    course_latest_status = {}
    for r in records:
        course_latest_status[r["course_code"]] = r["result"]
        
    backlogs = sum(1 for status in course_latest_status.values() if status in ('FAIL', 'ABSENT'))
    return backlogs

def list_rules(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rule_registry")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
