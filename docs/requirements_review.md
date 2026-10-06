# Review against the supplied participant guide

Reviewed all 16 scanned PDF pages in `New Doc 10-06-2026 11.01.pdf`, including sections
1–10 and Annexes A–E. The PDF is a project specification; it is not ingested as university
policy. Student data remains wholly synthetic.

| Contract | Implementation / evidence |
|---|---|
| R1–R3 · Grounded answers, citations, abstention | MiniLM + persistent Chroma; authority-aware evidence; source labels and clause/page/version/date; missing subject/rules abstain. A publisher's unspecified date is shown explicitly rather than fabricated. |
| R4 · Versions and conflicts | Date/programme/batch filters, explicit supersession, authority, recency and unresolved conflict response. Two future synthetic notices exercise date filtering and conflicts while today's public rule remains 75%. |
| R5 · Deterministic tools | SQLite tools and rule registry perform arithmetic and eligibility. A bounded LLM proposes tool names; code validates the required operations and supplies identity and parameters. Invalid plans fall back to the fixed workflow. |
| R6 · Multi-step | Attendance projections fetch records, calculate future attendance and compare the cited rule; assumptions are displayed, and no database record is edited. Unsupported placement rules abstain. |
| R7–R8 · Privacy and document instructions | Header-only student identity, other-ID refusals, missing-identity refusals, no real student records, unnecessary names removed from tool audit; document instructions cannot change tool identity or rule precedence. |
| R9–R10 · Types and audit | All six response types; trace, sources, dropped evidence, tool input/output, rules, conflicts, bounded plan, model, tokens and latency. No chain-of-thought. |
| R11 · Live ingestion | POST /ingest indexes immediately; explicit numeric level-1/2 attendance amendments update the rule registry. Single-line numbered clauses are retained. |
| R12 / section 7 · Evaluation | 37 questions: at least 3 unanswerable, 3 version/conflict, 4 personal, 2 foreign-ID and 2 successful multi-step questions. Two live retrieval configurations compared; reviewed clause prefixes checked where specified. |
| Section 4 / Annex B | 3 university-linked public PDFs plus the permitted 2 clearly marked synthetic notices; register, provenance and public-PDF checksums. No student rosters or result lists. |
| Section 4 / Annexes C and E | 32 students, 2 programmes, 2 batches, 10 courses; fixed required columns retained; documented prompts, local LLM output/validation and deterministic numerical edge cases. Validation report has 0 violations. |
| Section 5 / section 6 | Streamlit, FastAPI/Uvicorn/Pydantic v2, LangGraph, persistent Chroma, SQLite, sentence-transformers and local Ollama. Mandatory endpoints and loader provided. |
| Section 8 · Artifacts | Setup, architecture, source/rule registers, synthetic kit, benchmark comparison, sample audits and AI disclosure. |

Measured checks: 61 offline tests passed; the real-model default benchmark passed 37/37
expected answers and 27/27 citation checks. See the report for the exact scoring method,
comparison and latency. These are development checks, not a claim of universal accuracy.

Remaining external checks: Docker packaging is updated, but a Docker engine is not
installed here and sudo requires interactive authentication, so `docker compose up`
has not been run. Git metadata is unavailable in this mounted workspace; no tag, commit,
push or merge was made. Team contribution names/review need the team's own completion.

Known limits: historical public versions have no exact publisher-specified start dates;
placement thresholds are unavailable; only explicit minimum-attendance amendments are
extracted automatically into executable rules. Arbitrary new policies need reviewed
rule rows before deterministic eligibility can use them. The schema/marks fixture is a
demonstration, not a real NSUT transcript or a model of every relative-grading rule.
