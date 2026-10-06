# University Student Services Assistant

HCLTech Future Ready AI Engineer Hackathon — AI-Powered University Student Services Assistant.

**Current local profile: NSUT.** The app uses three university-linked public policy PDFs
and the user-provided historical fee notice
with entirely fictional student records, two clearly marked future synthetic conflict notices,
and a fictional lower-authority handbook for demonstrating resolved conflicts.
See [`data/nsut/README.md`](data/nsut/README.md)
for source provenance and supported rules, and [`docs/local_setup.md`](docs/local_setup.md)
to run it. The original synthetic policy examples below remain regression fixtures;
their 80% attendance and supplementary/placement rules are not NSUT policies.

> The model understands. Documents provide university policy. Tools provide personal student facts.
> Code makes deterministic decisions. The model explains the verified result.

## Architecture

```
Student ──▶ Streamlit UI ──▶ FastAPI /ask  (X-Student-Id header, as_of_date)
                                  │
                       ONE LangGraph workflow, six nodes, no loops, no autonomous agents
                                  │
   classify_query ──┬─ policy ───────────▶ retrieve_documents ───────────────┐
   (keyword routing,├─ personal ─────────▶ execute_tools ────────────────────┤
    header-only id) ├─ eligibility ──────▶ retrieve_documents → execute_tools┤
                    ├─ multi_step ───────▶ retrieve_documents → execute_tools┤
                    └─ clarification / refused ──────────────────────────────┤
                                                                             ▼
          resolve_sources_and_rules ──▶ generate_answer ──▶ validate_and_audit ──▶ JSON + citations
          (Annex A precedence, CODE)     (LLM explains)      (citations, id scrub, audit row)

   retrieve_documents → ChromaDB (persisted)      execute_tools → SQLite tools + rule_registry
```

| Layer | Choice | Why |
|---|---|---|
| Retrieval | ChromaDB + all-MiniLM-L6-v2 + BM25 reranking | small English policy corpus; CPU embeddings leave GPU memory for the LLM (`EMBEDDING_PROVIDER=bge` to switch) |
| Precedence | `app/rules/precedence.py` | Annex A in code: applicability by `as_of_date` + scope → clause-level supersession (level 1/2 only) → authority → recency → `conflict_flagged`. Semantic similarity decides what is *relevant*; metadata decides what is *applicable* |
| Student facts | SQLite + `app/tools/student_tools.py` | attendance %, results, backlogs computed by Python; shown with inputs/outputs in every response |
| Rules | `rule_registry` + `app/rules/eligibility.py` | every threshold is a registry row pointing at a cited clause; a circular that changes a threshold is a new row with its own `effective_from` |
| Orchestration | LangGraph, one `StateGraph` | different question types need different steps; routing stays visible and testable. We did **not** add agents: classification, precedence and eligibility are deterministic, so an agent would add latency and remove auditability |
| LLM | Ollama `llama3.1:8b` (primary) → optional cloud fallback → mock | proposes bounded tool names and explains verified facts; identity, arithmetic and calculated verdicts are supplied by code |
| UI | Streamlit | minimal portal; all logic lives behind the API |

Flowcharts: `docs/architecture.md`. Design decisions and the "why" for each: same file.

## Setup and run (local)

For the project-local Python/Ollama installation and the one-command launcher, see
[`docs/local_setup.md`](docs/local_setup.md). Once dependencies, data and models are ready,
run `.venv/bin/python scripts/run_local.py` to start the API and UI together.
For a fresh teammate checkout or the source ZIP, start with [`TEAM_SETUP.md`](TEAM_SETUP.md).

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

ollama pull llama3.1:8b                                   # do this BEFORE the event (or qwen2.5:7b-instruct)
python scripts/load_students.py --replace                 # validates then loads the configured synthetic records + rules
python scripts/ingest_documents.py                        # indexes the configured NSUT register into ChromaDB (persisted)
uvicorn app.main:app --reload --port 8000                 # API  → http://localhost:8000/docs
streamlit run ui/streamlit_app.py                         # UI   → http://localhost:8501
pytest tests -q                                           # offline tests (no Chroma/Ollama needed)
```

### Docker

```bash
cp .env.example .env
docker compose up --build           # API :8000, UI :8501; initializes missing data/index only
```
Ollama runs on the **host**; the container reaches it at `http://host.docker.internal:11434`
(set `DOCKER_OLLAMA_BASE_URL` if yours differs). The host Ollama listener must be reachable
from the Docker bridge; a localhost-only listener is insufficient. Use an existing reachable
Ollama endpoint for this command. The embedding model is baked into the image.
Docker runtime verification is pending because this workstation has no Docker engine.

### LLM configuration (disclosure)

Primary model is local Ollama (`OLLAMA_MODEL`). A cloud model is used **only** if `CLOUD_FALLBACK=true`
and Ollama fails; set `CLOUD_PROVIDER` (`openai`-compatible or `anthropic`), `CLOUD_API_KEY`, `CLOUD_MODEL`.
With `MOCK_FALLBACK=true` the last resort is a deterministic mock so the demo never shows a stack trace;
the audit record's `model` field always says which provider answered. `MOCK_LLM=true` runs everything
with the mock (used by tests and `scripts/evaluation.py --offline`).

## API (guide §6)

```bash
# policy fact (no identity needed)
curl -s localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is the minimum attendance required to appear for end-semester exams?"}' | jq

# future synthetic conflict example; these notices are not university-issued
curl -s localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is the minimum attendance required to appear for end-semester exams?","as_of_date":"2026-11-01"}' | jq .answer

# personal / eligibility / what-if — identity ONLY from the header
curl -s localhost:8000/ask -H 'Content-Type: application/json' -H 'X-Student-Id: S1006' \
  -d '{"question":"If I attend the next 4 classes, will I be eligible for the end-semester exam in DBMS?"}' | jq

# refused: another student's id in the text
curl -s localhost:8000/ask -H 'Content-Type: application/json' -H 'X-Student-Id: S1001' \
  -d '{"question":"Show attendance of S1002"}' | jq .answer_type

# live ingestion example (synthetic notice, searchable immediately)
# Reindexes an existing demo ID; no extra synthetic policy document is added.
curl -s -F file=@data/nsut/documents/demo-attendance-a.md \
  -F metadata='{"doc_id":"DEMO-ATT-A","title":"Synthetic attendance notice A — not university-issued","issuer":"Synthetic demo","authority_level":2,"doc_type":"circular","version":"demo-1.0","effective_from":"2026-11-01","supersedes":"NSUT-BTECH-2019#11.2","scope_programmes":"BTech","scope_batches":"2019+","synthetic":"Y"}' \
  localhost:8000/ingest | jq
# (.md files with front matter need no metadata; PDFs do)

curl -s localhost:8000/sources | jq          # Source Register
curl -s localhost:8000/audit/<trace_id> | jq # full audit record
curl -s localhost:8000/health | jq           # API, vector store, SQLite, LLM, embeddings

# judges' test students (Annex C CSVs) — CLI or endpoint
python scripts/load_students.py --dir test_students/
curl -s -F files=@test_students/students.csv -F files=@test_students/attendance.csv \
     -F files=@test_students/results.csv -F files=@test_students/courses.csv localhost:8000/admin/load-students
```

Response shape (`/ask`): `trace_id, answer, answer_type, citations[{doc_id,title,section,page,version,effective_from}],
tools_invoked[{tool,input,output,status,ms}], applied_rules[{rule_id,value,source_doc_id}], conflicts_detected[],
explanation, as_of_date` plus `verdict, assumptions, upcoming_changes` for the UI.

For a clarification follow-up, send the prior response's `trace_id` as the optional
`previous_trace_id` in the next `/ask` request. The account header and policy date must
match. Short topic/course replies continue the pending question; a fresh question starts
its own request. `clarification_options` supplies topic buttons or courses from the demo
account. Audits preserve the typed message, the completed question and prior trace.

## Deliverables map

| Item | Where |
|---|---|
| Source Register + documents | Active: `data/nsut/source_register.csv`, `data/nsut/documents/`; original fixtures: `data/source_register.csv`, `data/documents/` |
| Rule registry (every rule → cited clause) | Active: `data/nsut/rule_registry.csv` → SQLite `rule_registry`; original fixtures: `data/synthetic/rule_registry.csv` |
| Synthetic data kit | Active: `data/nsut/synthetic/`; original kit and prompts: `data/synthetic/`; `scripts/prepare_nsut_students.py`, `scripts/validate_students.py` |
| Evaluation set + report | Active: `data/evaluation/nsut_questions.jsonl` (37 q), `docs/nsut_evaluation_report.md`; original fixtures: `data/evaluation/questions.jsonl`, `docs/evaluation_report.md`; runner: `scripts/evaluation.py` |
| Sample audit records | `docs/sample_audits/` (`scripts/make_sample_audits.py`) |
| AI-usage disclosure | `docs/ai_usage_disclosure.md` |
| Team contribution | `docs/team_contribution.md` (fill in) |
| Demo script | `docs/demo_script.md` |

## Assumptions

- The active NSUT profile includes **three university-linked public policy documents,
  the user-provided fee notice, and two future synthetic demo notices**.
  All student records are synthetic. Original non-NSUT policy fixtures are used only in regression tests.
  Add verified public policies to the active register and run `python scripts/ingest_documents.py`.
  Clause numbers and PDF page numbers are detected for citations and precedence.
- A document with no metadata is ingested at authority level 5 (unofficial): it can be cited when nothing
  official answers, but never overrides an official source.
- `supersedes` uses Annex B syntax: `DOC`, `DOC#7.2`, several separated by `;`. Only level 1/2 documents supersede.
- `scope_batches` accepts `ALL`, `2023+`, `2023;2024`, `2021-2023`. `scope_programmes` matches ignoring punctuation (`B.Tech CSE` = `BTech CSE`).
- Course names in questions are resolved against the `courses` table (code, full name, initials, common abbreviations such as DBMS/OS/DS), preferring the signed-in student's own courses; judges' `JDG*` courses work the same way.
- Backlogs are derived from `results` (latest result per course not PASS); `students.active_backlogs` is validated against that.

## Limitations and known edge cases

- If a local model omits `[S#]` labels, evidence attribution checks supporting terms and every stated figure; unsupported answers abstain. Labelled citations and prose still need human review beyond the measured benchmark. Numbers in calculated answers are written by code.
- Conflict detection compares stated figures (percent, CGPA, marks, times…) in sentences that share ≥2 terms with the question; prose-only conflicts (no numbers) are not auto-detected.
- OCR is enabled in this local setup and packaged in Docker; it requires tesseract/poppler plus the Python OCR dependencies.
- `current_semester` aggregate attendance uses courses of that semester only; a student with no attendance rows in the current semester fails the placement attendance check with a clear "no record" tool status.
- CGPA in the synthetic data is assigned, not computed from marks.
- Audit records store the question, student id and tool inputs/outputs (needed to reproduce the answer) — nothing else personal.
