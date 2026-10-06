
🗄️ Student Data Tools (Deterministic Queries Layer)
This module provides the deterministic, SQLite-backed tools for the AI-Powered University Student Services Assistant. It acts as the "ground truth" execution layer, ensuring that the LLM never guesses or hallucinates a student's personal academic data, attendance, or exam eligibility.

🎯 Architecture & Core Principles
Zero LLM Arithmetic: All percentages and derived metrics (e.g., attendance percentage) are strictly calculated on the fly using standard Python logic. The LLM only receives the final, verified numbers.

Dynamic Rule Enforcement: Thresholds (like "75% minimum attendance") are never hardcoded. Tools dynamically query the rule_registry table, ensuring that policy updates seamlessly take effect without altering Python code.

Strict Authorization: All queries use parameterized SQL execution (?) and mandate the student_id (extracted securely via the X-Student-Id header) to prevent prompt injection and cross-account access.

Automated Citation Routing: Every policy evaluation returns the explicit source_doc_id and source_section from the registry, enabling the LangGraph orchestrator to provide perfectly grounded answers.

📂 File Structure
Plaintext
/
├── deterministic_queries/
│   ├── student_data_tools.py   # Core Python functions meant to be wrapped by @tool
│   └── create_test_db.py       # Script to generate the schema and synthetic edge-case data
├── test_students/              # Annex C compliant CSV files for production data loading
│   ├── students.csv
│   ├── attendance.csv
│   └── rule_registry.csv
└── university.db               # The local serverless SQLite database (Git-ignored)
🚀 Setup & Testing
1. Initialize the Database:
Generate the local university.db file and populate it with synthetic student records and edge cases.

Bash
python deterministic_queries/create_test_db.py
2. Test the Tools:
Run a quick test to verify that the dynamic thresholding is working correctly (e.g., verifying a student exactly at the 75% boundary).

Bash
python -c "from deterministic_queries.student_data_tools import check_exam_eligibility; print(check_exam_eligibility('S1002', 'CS201'))"
🛠️ Available Tools for LangGraph Integration
These functions are designed to be imported into agent.py and wrapped with LangChain's @tool decorator.

get_attendance(student_id: str, course_code: str) -> dict
Queries the database for raw classes_held and classes_attended, computes the exact attendance percentage deterministically, and returns the structured dictionary.

check_exam_eligibility(student_id: str, course_code: str) -> dict
Fetches a student's calculated attendance and dynamically compares it against the active threshold in the rule_registry table. Returns ELIGIBLE or DETAINED, alongside the applied rule metadata for citation routing.

🔄 Updating Policies
To update a university rule (e.g., a new circular changes passing marks), do not edit the Python code. Simply execute an UPDATE SQL statement on the rule_registry table. The Python tools will immediately inherit and apply the new policy on the next execution.
