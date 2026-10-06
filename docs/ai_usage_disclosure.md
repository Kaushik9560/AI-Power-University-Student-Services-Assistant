# AI-usage disclosure

OpenAI Codex assisted with the NSUT adaptation, local dependency/GPU setup and launcher,
source registration, retrieval ranking, rule precedence, deterministic tools and attendance
projections, bounded model tool planning, citation attribution, audit records, OCR ingestion,
Streamlit redesign, evaluations, regression tests and documentation. The existing scaffold
predated this session; its earlier disclosure attributed it to an Anthropic coding assistant.
That earlier model attribution has not been independently verified.

The active fictional names were generated with local Ollama `llama3.1:8b`. Exact prompts,
three raw responses, count-validation errors and deterministic assembly of 32 unique names
are preserved in `data/nsut/synthetic/generation_run.json` and `prompts.md`. Numerical
student records are deliberate synthetic fixtures, including boundary/failed/absent/detained
cases; they are not extracted from real students. See `data_card.md` for the full provenance
and the grading-model limits.

Public NSUT policies were retrieved through its official document links. No private university
system or real student dataset was accessed. The two future conflict notices are explicitly
synthetic, not university-issued. The participant guide was read as a specification and was
not ingested as policy evidence.

Verification: 61 offline tests; synthetic CSV validation with zero violations; 37 real-model
development questions with two retrieval configurations; clause/page checks where specified;
browser and HTTP checks; isolated live-ingestion and immediate rule-update checks. The
report distinguishes measured known cases from arbitrary unseen questions. The default
configuration passed 37/37 expected answers and 27/27 citation checks in the recorded run.

Code supplies identity, arithmetic, rule thresholds, source precedence and calculated verdicts.
The model proposes a constrained tool-name list and explains facts; invalid plans fall back
to code. Audit records disclose the actual provider, bounded plan, inputs/outputs, tokens
and latency without chain-of-thought or unnecessary student names.

Examples of corrected failures: stale terminal variables selected an empty non-NSUT index;
missing model labels attributed an answer to the wrong top-ranked source; single-line numbered
clauses vanished during ingestion; incomplete model-generated name lists failed validation.
These were corrected through explicit profile loading, evidence attribution/abstention,
inline-clause retention and recorded deterministic name assembly.

Team members must fill and review their own ownership entries in `docs/team_contribution.md`.
Docker runtime verification and Git tagging are pending in this workstation environment.
