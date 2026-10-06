# Synthetic NSUT demo data card (Annex E)

| Field | Detail |
|---|---|
| Purpose | Exercise attendance boundaries, sourced eligibility, hypothetical future attendance, failed/absent/detained results, backlogs and privacy without accessing any real student system. Course names/codes and assignments are fixtures, not an official NSUT course catalogue. |
| Generator | Local Ollama `llama3.1:8b` generated the fictional names at temperature 0.4 in 3 calls. IDs and numerical records derive from the original seeded synthetic kit; `scripts/prepare_nsut_students.py` applies NSUT demo edges. |
| Prompts | `prompts.md` contains the exact system/user prompts. `generation_run.json` retains the exact model, outputs, call count, validation errors and normalization/assembly method. |
| Schema enforcement | Required Annex C columns are preserved. Pydantic validates 32 distinct full names; JSON fences/array shape are normalized. The independent CSV validator checks identity formats, references, programmes, attendance bounds, mark sums/ranges and derived backlogs. |
| Counts | 32 students; 8 in each programme/batch group (B.Tech CSE/ECE × 2023/2024); 10 courses; 144 attendance rows; 97 result rows: 85 PASS, 10 FAIL, 1 ABSENT, 1 DETAINED. |
| Deliberate edges | S1005 DBMS 75/100 exactly at the attendance threshold; S1006 74/100 one class below; S1007 65/100; S1008 60/100. S1007 has a failed-course example, S1008 an absent result, S1002 a detained result, S1009 three backlogs. Original 39/100 and assigned CGPA examples are retained. |
| NSUT adaptations | The previous synthetic supplementary pass is represented as a regular repeat-course result because public clause 12.3 provides no supplementary exams. Fictional failed rows with external marks ≥18 are reduced to 17/60 and totals recomputed. All values remain demonstration records. |
| Validation | `validation_report.txt`: 0 violations. Loader upserts transactionally; failed replacements roll back. No student IDs S9000–S9999 or JDG course codes are generated; those remain reserved for judges. |
| LLM errors and fixes | Every generation returned 31 names rather than 32, with one array instead of an object and one markdown fence. Code normalized JSON and assembled 32 unique, unchanged model-generated names from the partial responses, then validated the final count and uniqueness. Original errors remain in the run record. |
| Limitations | CGPA is assigned rather than derived from grades. Numerical 40/60 mark fixtures do not model every NSUT theory/practical assessment scheme or relative grade boundary. No placement cutoff was verified. Validation does not reconstruct a real transcript. |

Every identity, attendance count, mark, CGPA and result is fictional. No roster, individual
result notice, scholarship application or private university database was accessed.
Regenerate with `python scripts/prepare_nsut_students.py --llm-names`, or reproduce the
recorded names without another model call using `--replay data/nsut/synthetic/generation_run.json`.
