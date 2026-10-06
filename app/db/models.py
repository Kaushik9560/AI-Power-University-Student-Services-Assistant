"""OWNER: student-data. TODO step 2: define student record models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Student:
    """Minimal student identity expanded by the student-data area."""

    student_id: str
    name: str
