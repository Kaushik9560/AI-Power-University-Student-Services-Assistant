# University Student Services Assistant

HCLTech Future Ready AI Engineer Hackathon — AI-Powered University Student Services Assistant.

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
| Retrieval | ChromaDB + all-MiniLM-L6-v2 | small corpus, short English questions; MiniLM is ~3× faster than bge-small on CPU with no measurable difference on our eval set (`EMBEDDING_PROVIDER=bge` to switch) |
| Precedence | `app/rules/precedence.py` | Annex A in code: applicability by `as_of_date` + scope → clause-level supersession (level 1/2 only) → authority → recency → `conflict_flagged`. Semantic similarity decides what is *relevant*; metadata decides what is *applicable* |
| Student facts | SQLite + `app/tools/student_tools.py` | attendance %, results, backlogs computed by Python; shown with inputs/outputs in every response |
| Rules | `rule_registry` + `app/rules/eligibility.py` | every threshold is a registry row pointing at a cited clause; a circular that changes a threshold is a new row with its own `effective_from` |
| Orchestration | LangGraph, one `StateGraph` | different question types need different steps; routing stays visible and testable. We did **not** add agents: classification, precedence and eligibility are deterministic, so an agent would add latency and remove auditability |
| LLM | Ollama `llama3.1:8b` (primary) → optional cloud fallback → mock | the LLM only writes prose from verified facts; the one-line answer for calculated results is written by code |
| UI | Streamlit | minimal portal; all logic lives behind the API |

Flowcharts: `docs/architecture.md`. Design decisions and the "why" for each: same file.

## Setup and run (local)

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

ollama pull llama3.1:8b                                   # do this BEFORE the event (or qwen2.5:7b-instruct)
python scripts/load_students.py --replace                 # validates then loads data/synthetic/*.csv + rule registry
python scripts/ingest_documents.py                        # indexes data/source_register.csv into ChromaDB (persisted)
uvicorn app.main:app --reload --port 8000                 # API  → http://localhost:8000/docs
streamlit run ui/streamlit_app.py                         # UI   → http://localhost:8501
pytest tests -q                                           # 32 offline tests (no Chroma/Ollama needed)
```

### Docker

```bash
cp .env.example .env
docker compose up --build           # API :8000, UI :8501; loads data and ingests the register on start
```
Ollama runs on the **host**; the container reaches it at `http://host.docker.internal:11434`
(set `OLLAMA_BASE_URL` in `.env` if yours differs). The embedding model is baked into the image.

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

# same question as of a date before the circular took effect
curl -s localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is the minimum attendance required to appear for end-semester exams?","as_of_date":"2025-10-01"}' | jq .answer

# personal / eligibility / what-if — identity ONLY from the header
curl -s localhost:8000/ask -H 'Content-Type: application/json' -H 'X-Student-Id: S1001' \
  -d '{"question":"I failed Data Structures. If I pass the supplementary, will I be eligible for placement?"}' | jq

# refused: another student's id in the text
curl -s localhost:8000/ask -H 'Content-Type: application/json' -H 'X-Student-Id: S1001' \
  -d '{"question":"Show attendance of S1002"}' | jq .answer_type

# live ingestion (multipart: file + Source Register metadata JSON) — searchable immediately
curl -s -F file=@data/documents/demo/CIR-ACAD-2026-09-JUDGE-EXAMPLE.md \
  -F metadata='{"doc_id":"CIR-ACAD-2026-09","title":"Revision of Condonation Limit","issuer":"Dean (Academics)","authority_level":2,"doc_type":"circular","version":"1.0","effective_from":"2026-10-01","supersedes":"ACAD-REG-2024#7.3","scope_programmes":"ALL","scope_batches":"2024+","synthetic":"Y"}' \
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

## Deliverables map

| Item | Where |
|---|---|
| Source Register + documents | `data/source_register.csv`, `data/documents/` (demo-only docs in `data/documents/demo/`) |
| Rule registry (every rule → cited clause) | `data/synthetic/rule_registry.csv` → SQLite `rule_registry` |
| Synthetic data kit | `data/synthetic/`: `prompts.md` (verbatim), `data_card.md`, `validation_report.txt`, `scripts/generate_students.py`, `scripts/validate_students.py` |
| Evaluation set + report | `data/evaluation/questions.jsonl` (30 q), `scripts/evaluation.py`, `docs/evaluation_report.md` |
| Sample audit records | `docs/sample_audits/` (`scripts/make_sample_audits.py`) |
| AI-usage disclosure | `docs/ai_usage_disclosure.md` |
| Team contribution | `docs/team_contribution.md` (fill in) |
| Demo script | `docs/demo_script.md` |

## Assumptions

- **Documents are synthetic placeholders.** The guide requires your own university's public documents
  (minimum 3 real, at most 2 synthetic). Replace the `.md` files and the register rows with real PDFs before
  submission: drop the PDF in `data/documents/`, add a register row (`file` column), run
  `python scripts/ingest_documents.py`. Clause numbers inside PDFs (e.g. `7.2 Minimum attendance`) are detected
  automatically for clause-level supersession and citations; pages are recorded.
- A document with no metadata is ingested at authority level 5 (unofficial): it can be cited when nothing
  official answers, but never overrides an official source.
- `supersedes` uses Annex B syntax: `DOC`, `DOC#7.2`, several separated by `;`. Only level 1/2 documents supersede.
- `scope_batches` accepts `ALL`, `2023+`, `2023;2024`, `2021-2023`. `scope_programmes` matches ignoring punctuation (`B.Tech CSE` = `BTech CSE`).
- Course names in questions are resolved against the `courses` table (code, full name, initials, common abbreviations such as DBMS/OS/DS), preferring the signed-in student's own courses; judges' `JDG*` courses work the same way.
- Backlogs are derived from `results` (latest result per course not PASS); `students.active_backlogs` is validated against that.

## Limitations and known edge cases

- A local 7–8B model occasionally omits `[S#]` labels; the validator then cites the top-ranked source and logs the fact in `errors`. It never changes a number: numbers in calculated answers are written by code.
- Conflict detection compares stated figures (percent, CGPA, marks, times…) in sentences that share ≥2 terms with the question; prose-only conflicts (no numbers) are not auto-detected.
- OCR is optional (`OCR_ENABLED=true` + tesseract/poppler); without it a scanned PDF page with no text layer is skipped.
- `current_semester` aggregate attendance uses courses of that semester only; a student with no attendance rows in the current semester fails the placement attendance check with a clear "no record" tool status.
- CGPA in the synthetic data is assigned, not computed from marks.
- Audit records store the question, student id and tool inputs/outputs (needed to reproduce the answer) — nothing else personal.
