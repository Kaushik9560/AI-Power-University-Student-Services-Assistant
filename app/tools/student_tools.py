"""OWNER: student-data. TODO step 2: implement plain student data functions."""

from typing import Any


class ToolError(RuntimeError):
    """Raised when a student tool cannot produce a trustworthy result."""


def get_student(student_id: str) -> dict[str, Any]:
    """Return one student record or raise ``ToolError``."""

    raise ToolError(f"Student lookup is not implemented for {student_id}")
