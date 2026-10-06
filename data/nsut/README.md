# NSUT policy profile

This profile combines public NSUT policy PDFs with fictional student records.
It contains no real student identities, attendance, marks, results or scholarship applications.
Student rosters and individual-result notices are excluded.

The official [Educational Programmes index](http://www.nsut.ac.in/en/educational-programmes)
links the B.Tech regulations and Ordinance II. The official
[Policies and Guidelines index](http://www.nsut.ac.in/en/policies-and-guidelines) links the
CVSPK scholarship rules. Those university-linked Google Drive PDFs were downloaded on
2026-10-06. `source_register.csv` records their original URLs; `document_checksums.json`
records SHA-256 checksums of the originals.

| Document | Relevant clauses | PDF pages |
|---|---|---|
| B.Tech Regulations 2019-I(A) | 11.2: 75% attendance; 11.3: up to 10% relaxation with approval and evidence; 11.4: exceptional further relaxation; 12.3: no supplementary exams; 15.1: degree requirements | attendance 18, repeat courses 19, degree 20 |
| Ordinance II | Scope, governance and authority for undergraduate/postgraduate programmes | 1–3 |
| CVSPK Rules 2020 | Talent incentives, FWS assistance and blank application forms | talent scheme 11–16, FWS 18–24 |
| User-provided FEE_NOTICE.pdf (library title FEE_2026) | Historical fee structure for the 2022–23 admission cohort; regular/summer course re-registration fees | re-registration 17 |

The user-uploaded fee notice is retained with its existing document ID and metadata,
including the user-entered applicability date, so a fresh teammate setup can rebuild
the same library. Its published admission cohort is **2022–23**. No official download
URL was supplied for this upload; its provenance differs from the three university-linked
PDFs above. The title FEE_2026 does not establish a new fee policy for 2026 admissions.

The PDFs specify an academic session rather than an exact commencement date. Accordingly,
`effective_from` is blank; no precise date or supersession relationship has been invented.
The documents are the versions linked by the public site on the retrieval date. Later campus
circulars may change them; those must be checked and ingested with their actual metadata.
The B.Tech PDF's cover has blank approval-meeting fields, which are preserved as published.

`rule_registry.csv` contains three baseline rules grounded in these PDFs. Explicit numeric
minimum-attendance amendments from level-1/2 sources add metadata-linked `AUTO-*` rules
on ingestion. Placement thresholds
were not found in these sources, so personal placement eligibility abstains. Additional
attendance relaxation under clause 11.4 needs a committee recommendation; the app does
not grant an approval or automatically lower the attendance requirement.

The original ten synthetic policy fixtures under `data/documents/` and the original register
remain for regression tests. They are not loaded into the active NSUT collection.

Two active synthetic notices, `DEMO-ATT-A` and `DEMO-ATT-B`, deliberately disagree at 80%
and 85%, effective **2026-11-01**. They are clearly marked as not university-issued and
exercise future-date filtering and unresolved conflicts. They do not change today's 75% rule.

`DEMO-ATT-HANDBOOK` is a fictional level-4 handbook stating 70%, effective
**2026-10-07**. On that date the level-1 B.Tech regulation's 75% prevails by
authority. The losing handbook clause is excluded from the answer evidence, and
the disagreement is recorded in the audit as `resolved_by: authority`. This fixture
does not supersede any regulation or create an eligibility rule. All three demo
documents are clearly marked as not university-issued.

The active fictional names were generated with local Ollama; raw outputs, validation and
deterministic repair of incomplete responses are preserved in `synthetic/generation_run.json`.
See `synthetic/data_card.md` for provenance and schema limitations. To regenerate with the
model, use `python scripts/prepare_nsut_students.py --llm-names`, then validate and load
with the scripts described in `docs/local_setup.md`.
