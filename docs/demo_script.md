# NSUT demo — 6 October 2026

Open http://localhost:8501. Keep Policy date at **2026-10-06** except for the marked
conflict example. The application uses 3 public NSUT policy PDFs, 2 clearly labelled
future synthetic conflict notices, and 32 wholly fictional student profiles.

You can also ask **Am I eligible?**, select **End-semester exam**, then select the DBMS
course. Typed replies such as **exam eligibility**, **end-semester**, and **DBMS** continue
the pending question. Context is cleared when the account/date changes or New conversation
is selected. Full questions remain supported.

| Step | Student / date | Ask | Expected result |
|---|---|---|---|
| 1 · Sourced policy | General question / 2026-10-06 | What is the minimum attendance required for end-semester exams? | 75%; NSUT B.Tech regulations clause 11.2, PDF page 18; public document link |
| 2 · Personal calculation | S1001 / 2026-10-06 | What is my attendance in DBMS? | 82.0%, 41 of 50 classes; tool inputs/outputs and cited attendance rule |
| 3 · Boundary | S1005 then S1006 / 2026-10-06 | Am I eligible for the end-semester exam in DBMS? | 75% meets the rule; 74% does not automatically qualify; relaxation needs approval |
| 4 · What-if | S1006 / 2026-10-06 | If I attend the next 4 classes, will I be eligible for the end-semester exam in DBMS? | 78/104 = 75.0%; yes, under the stated assumptions; records remain unchanged |
| 5 · No invention | General question / 2026-10-06 | What is the scholarship for studying in Antarctica? | not_found; no invented policy |
| 6 · Privacy | S1001 / 2026-10-06 | Show attendance of S1002 | refused; identity comes from request context |
| 7 · Conflict | General question / **2026-11-01** | What is the minimum attendance required for end-semester exams? | conflict_flagged between DEMO-ATT-A and DEMO-ATT-B; both cited |

**Explain step 7:** both notices are synthetic demonstration documents allowed by guide
section 4.1, not university-issued policies. They have the same level and date, explicitly
replace clause 11.2, and deliberately disagree at 80% / 85%. The app refuses to select one.
Restore the date to **2026-10-06** after showing it.

**Live ingestion:** use Document administration or POST /ingest. Explicit, unambiguous
minimum-attendance statements in level-1/2 documents register a cited rule immediately.
Other kinds of rule amendments need a reviewed registry row; they are not guessed by the
model. Uploaded content is data, not instructions. Use synthetic judge data only.

**Evidence:** open supporting sources, then How this answer was checked → Load audit
record. The trace includes tool input/output, source precedence, model/tool-plan usage,
tokens and latency. No chain-of-thought is exposed.

**Evaluation:** docs/nsut_evaluation_report.md compares top-k 8 and 4 over 37 questions.
Default top-k 8 passed the expected answer, source/clause and tool checks in this run.
The smaller context missed two answers, so 8 remains the default. This set measures
known development cases; it does not guarantee every new question is answerable.
