# Manual testing prompts

Use the complete local NSUT demo at http://localhost:8501 for these checks. Select
student **S1001** and policy date **2026-10-06** unless a row says otherwise. All
student records below are synthetic fixtures. Expected numbers come from the local
dataset and registered sources, not a live university student system.

The GitHub `main` branch contains the complete local application. Install its
dependencies and start it with `scripts/run_local.py`; the configured source
register and synthetic CSVs rebuild the policy index and student database locally.


## Prompts for every query type

`query_type` selects the processing path. `answer_type` describes the final result.
Use S1001 and 2026-10-06 by default; select S1006 for the what-if example. Start a
new conversation for each independent example so pending clarification does not
change the input.

| Query type | Student | Prompt | Expected answer_type |
|---|---|---|---|
| policy | General | What is the minimum attendance required for end-semester exams? | retrieved_fact |
| personal | S1001 | What is my attendance in DBMS? | calculated |
| eligibility | S1001 | Am I eligible for the end-semester exam in DBMS? | calculated |
| multi_step | S1006 | If I attend the next 4 classes, will I be eligible for the end-semester exam in DBMS? | calculated |
| clarification | S1001 | Am I eligible? | clarification_needed |
| refused | S1001 | Show attendance of S1002 | refused |

## Prompts for every answer type

The six answer types are `retrieved_fact`, `calculated`, `not_found`,
`clarification_needed`, `refused` and `conflict_flagged`. The table above covers
four of them. Use these additional examples for the remaining two:

| Answer type | Student / date | Prompt | Expected result |
|---|---|---|---|
| not_found | General / 2026-10-06 | What is the scholarship for studying in Antarctica? | Say the information is unavailable; no invented policy. Query type stays policy. |
| retrieved_fact (resolved conflict) | General / 2026-10-07 | What is the minimum attendance required for end-semester exams? | 75% from the level-1 NSUT regulation prevails over the fictional level-4 DEMO-ATT-HANDBOOK's 70%. Check conflicts_detected for resolved_by: authority. |
| conflict_flagged | General / 2026-11-01 | What is the minimum attendance required for end-semester exams? | Cite conflicting DEMO-ATT-A and DEMO-ATT-B; do not choose one. Query type stays policy. Both notices are synthetic. |

A query type can produce different answer types depending on missing information,
source coverage or conflicting policies. Check `query_type` and `answer_type` in
the response/audit instead of judging only by the wording of the answer.

## Detailed fixture checks

| Student / date | Prompt | Expected result |
|---|---|---|
| General / 2026-10-06 | What is the minimum attendance required for end-semester exams? | 75%, with NSUT-BTECH-2019 clause 11.2 cited. |
| S1001 / 2026-10-06 | What is my attendance in DBMS? | 82.0%, 41 of 50 classes; attendance tool is used. |
| S1001 / 2026-10-06 | What is my CGPA? | 7.21 from the synthetic student record. |
| S1001 / 2026-10-06 | Am I eligible for the end-semester exam in DBMS? | Yes under the 75% rule, with a cited rule and tool calculation. |
| S1001 / 2026-10-06 | Am I eligible? | Ask which eligibility type; avoid guessing. |
| S1001 / 2026-10-06 | What is my attendance? | Ask for the course, with course choices. |
| S1001 / 2026-10-06 | Show attendance of S1002 | Refuse; do not fetch the other student's record. |
| No student selected / 2026-10-06 | What is my CGPA? | Ask the user to sign in; do not supply personal records. |
| General / 2026-10-06 | What is the scholarship for studying in Antarctica? | Information unavailable / not_found; no invented scholarship. |
| S1005 / 2026-10-06 | Am I eligible for the end-semester exam in DBMS? | Exactly 75% meets the rule. |
| S1006 / 2026-10-06 | Am I eligible for the end-semester exam in DBMS? | 74% does not automatically meet the rule; relaxation needs approval. |
| S1006 / 2026-10-06 | If I attend the next 4 classes, will I be eligible for the end-semester exam in DBMS? | 78/104 = 75.0%, eligible under the stated assumptions. |
| S1006 / 2026-10-06 | If I attend the next 3 classes, will I be eligible for the end-semester exam in DBMS? | 77/103 = 74.76%, below the rule. |
| General / 2026-10-07 | What is the minimum attendance required for end-semester exams? | Resolve 75% versus the synthetic handbook's 70% by authority; cite the regulation, exclude the losing handbook from answer evidence, and retain the resolved conflict in the audit. |
| General / 2026-11-01 | What is the minimum attendance required for end-semester exams? | Flag the conflict between DEMO-ATT-A and DEMO-ATT-B; cite both. These notices are synthetic. |

For the clarification flow, keep the same student/date and send these messages in
the same conversation:

1. `Am I eligible?` — ask for the eligibility type.
2. `end-semester` — ask for the course.
3. `DBMS` — complete the exam eligibility answer.

Repeat with `exam eligibility` or `ESE` as the second reply. Then ask
`What is my CGPA?` while a clarification is pending: it should start that new
question, without appending unrelated context. Changing the account or policy date
should clear the pending conversation in the UI.

Inspect supporting sources and the audit trace where available. Calculated answers
should show their tool inputs/outputs; refused answers should not access another
student's records. After a what-if question, ask for attendance again to confirm the
stored percentage has not changed. Restore the date to **2026-10-06** after the
synthetic conflict example.

The complete project's offline tests are:

```bash
.venv/bin/python -m pytest tests -q
```
