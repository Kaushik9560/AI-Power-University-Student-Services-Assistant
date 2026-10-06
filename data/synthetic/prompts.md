# Synthetic student data — verbatim generation prompts

These are the exact prompts used to produce the student roster (names, programmes, batches, CGPAs).
Attendance and result rows, and every edge case, are produced by code in `scripts/generate_students.py`
and validated by `scripts/validate_students.py`, because those values must satisfy arithmetic
constraints that an LLM gets wrong often enough to matter.

Generator used for the committed data: Claude Fable 5.1 (Anthropic), single session, the same prompt
below, with the output validated by the Pydantic models in `scripts/generate_students.py`.
`python scripts/generate_students.py --llm` re-runs the same prompt against the configured Ollama model.

## SYSTEM PROMPT

You generate synthetic university student records for a software test fixture. Output ONLY a JSON array,
no prose, no markdown fences. Every object must have exactly these keys and types:
student_id (string, "S" followed by 4 digits, 1001-1999 only — never 9000-9999),
full_name (string, Indian-style synthetic name, never a real person),
programme (string, one of "B.Tech CSE", "B.Tech ECE"),
batch_year (integer, 2023 or 2024),
current_semester (integer: 7 for batch 2023, 5 for batch 2024),
cgpa (number, 2 decimals, between 5.0 and 9.5, realistic distribution centred on 7.3),
active_backlogs (integer, always 0 — it is recomputed from results later).

## USER PROMPT

Generate 32 students: 8 per (programme, batch) combination, ids S1001..S1032 in order:
S1001-S1008 B.Tech CSE 2024, S1009-S1016 B.Tech CSE 2023, S1017-S1024 B.Tech ECE 2024, S1025-S1032 B.Tech ECE 2023.
Use these exact CGPAs where listed (edge cases), otherwise choose realistic values:
S1001 7.21, S1002 6.45, S1003 5.80, S1004 6.00, S1009 5.10, S1010 8.50.
All names must be distinct. Return the JSON array only.

## Schema enforcement

Each returned object is parsed into `Student` (Pydantic v2): regex on student_id, reserved-range check,
numeric bounds, name length. Any invalid row fails the whole batch; the script retries up to 3 times and
falls back to the deterministic seeded generator if the model cannot produce 30+ valid rows.
