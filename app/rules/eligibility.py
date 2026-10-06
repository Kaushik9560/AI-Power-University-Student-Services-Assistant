import operator
from dataclasses import dataclass
from typing import Optional, Any
from app.db.database import get_connection
from app.tools.student_tools import (
    ToolError,
    get_student,
    get_attendance,
    get_result,
    get_active_backlogs
)

@dataclass
class Verdict:
    status: str             # "ELIGIBLE", "DETAINED", "NOT_ELIGIBLE"
    rule_id: str
    parameter: str
    actual_value: Any
    threshold_value: Any
    operator: str
    source_doc_id: str
    source_section: str
    details: str

def evaluate(actual_val: Any, op_str: str, threshold_val: Any) -> bool:
    ops = {
        ">=": operator.ge,
        "<=": operator.le,
        ">": operator.gt,
        "<": operator.lt,
        "==": operator.eq,
        "=": operator.eq,
        "!=": operator.ne
    }
    
    if op_str in ops:
        return ops[op_str](float(actual_val), float(threshold_val))
    
    if op_str.lower() == "in":
        allowed = [x.strip() for x in str(threshold_val).split(",")]
        return str(actual_val) in allowed
        
    if op_str.lower() == "between":
        parts = [float(x.strip()) for x in str(threshold_val).split(",")]
        return parts[0] <= float(actual_val) <= parts[1]
        
    raise ToolError(f"Unsupported evaluation operator: '{op_str}'")

def get_applicable_rule(
    rule_id: str,
    programme: str = "ALL",
    batch_year: Optional[int] = None,
    as_of_date: str = "2026-10-06",
    db_path: Optional[str] = None
) -> dict:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    query = """
        SELECT * FROM rule_registry 
        WHERE rule_id = ? 
          AND (scope_programmes = 'ALL' OR scope_programmes LIKE ?)
          AND (scope_batches = 'ALL' OR scope_batches LIKE ?)
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to >= ?)
        ORDER BY effective_from DESC LIMIT 1
    """
    cursor.execute(query, (rule_id, f"%{programme}%", f"%{batch_year}%" if batch_year else "ALL", as_of_date, as_of_date))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise ToolError(f"Active rule '{rule_id}' not found for scope ({programme}, {batch_year}) as of {as_of_date}.")
    return dict(row)

def check_exam_eligibility(student_id: str, course_code: str, as_of_date: str = "2026-10-06", db_path: Optional[str] = None) -> Verdict:
    student = get_student(student_id, db_path)
    att = get_attendance(student_id, course_code, db_path)
    rule = get_applicable_rule("ATT-MIN-01", student["programme"], student["batch_year"], as_of_date, db_path)
    
    actual_pct = att["attendance_percentage"]
    threshold_pct = float(rule["value"])
    is_eligible = evaluate(actual_pct, rule["operator"], threshold_pct)
    
    return Verdict(
        status="ELIGIBLE" if is_eligible else "DETAINED",
        rule_id=rule["rule_id"],
        parameter=rule["parameter"],
        actual_value=actual_pct,
        threshold_value=threshold_pct,
        operator=rule["operator"],
        source_doc_id=rule["source_doc_id"],
        source_section=rule["source_section"],
        details=f"Attendance {actual_pct}% {'meets' if is_eligible else 'fails'} threshold of {rule['operator']} {threshold_pct}%."
    )

def check_supplementary_eligibility(student_id: str, course_code: str, as_of_date: str = "2026-10-06", db_path: Optional[str] = None) -> Verdict:
    student = get_student(student_id, db_path)
    result = get_result(student_id, course_code, db_path=db_path)
    rule = get_applicable_rule("SUPPL-MAX-01", student["programme"], student["batch_year"], as_of_date, db_path)
    
    if result["result"] not in ("FAIL", "ABSENT"):
        return Verdict(
            status="NOT_ELIGIBLE",
            rule_id=rule["rule_id"],
            parameter="result_status",
            actual_value=result["result"],
            threshold_value="FAIL/ABSENT",
            operator="in",
            source_doc_id=rule["source_doc_id"],
            source_section=rule["source_section"],
            details=f"Course {course_code} is already marked as {result['result']}."
        )
        
    backlogs = get_active_backlogs(student_id, db_path)
    max_backlogs = float(rule["value"])
    is_allowed = evaluate(backlogs, rule["operator"], max_backlogs)
    
    return Verdict(
        status="ELIGIBLE" if is_allowed else "NOT_ELIGIBLE",
        rule_id=rule["rule_id"],
        parameter=rule["parameter"],
        actual_value=backlogs,
        threshold_value=max_backlogs,
        operator=rule["operator"],
        source_doc_id=rule["source_doc_id"],
        source_section=rule["source_section"],
        details=f"Student has {backlogs} backlogs; maximum allowed is {max_backlogs}."
    )

def check_placement_eligibility(
    student_id: str,
    assume_cleared: bool = False,
    as_of_date: str = "2026-10-06",
    db_path: Optional[str] = None
) -> Verdict:
    student = get_student(student_id, db_path)
    cgpa_rule = get_applicable_rule("PLACE-CGPA-01", student["programme"], student["batch_year"], as_of_date, db_path)
    backlogs_rule = get_applicable_rule("PLACE-BACKLOG-01", student["programme"], student["batch_year"], as_of_date, db_path)
    
    cgpa_ok = evaluate(student["cgpa"], cgpa_rule["operator"], float(cgpa_rule["value"]))
    actual_backlogs = 0 if assume_cleared else get_active_backlogs(student_id, db_path)
    backlogs_ok = evaluate(actual_backlogs, backlogs_rule["operator"], float(backlogs_rule["value"]))
    
    eligible = cgpa_ok and backlogs_ok
    status = "ELIGIBLE" if eligible else "NOT_ELIGIBLE"
    details = f"CGPA: {student['cgpa']} ({'>=' if cgpa_ok else '<'} {cgpa_rule['value']}), Backlogs: {actual_backlogs} (hypothetical={assume_cleared})."
    
    return Verdict(
        status=status,
        rule_id=f"{cgpa_rule['rule_id']}+{backlogs_rule['rule_id']}",
        parameter="cgpa_and_backlogs",
        actual_value={"cgpa": student["cgpa"], "backlogs": actual_backlogs},
        threshold_value={"min_cgpa": cgpa_rule["value"], "max_backlogs": backlogs_rule["value"]},
        operator="composite",
        source_doc_id=cgpa_rule["source_doc_id"],
        source_section=cgpa_rule["source_section"],
        details=details
    )
