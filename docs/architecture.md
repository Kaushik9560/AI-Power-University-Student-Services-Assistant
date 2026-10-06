# Architecture & design decisions

> The model understands. Documents provide university policy. Tools provide personal student facts.
> Code makes deterministic decisions. The model explains the verified result.

## 1. The workflow (one LangGraph, six nodes)

```
Student ─▶ Streamlit UI ─▶ FastAPI /ask (X-Student-Id header, as_of_date)
                              │
   classify_query ─┬─ policy ──────────▶ retrieve_documents ──────────────┐
                   ├─ personal ────────▶ execute_tools ───────────────────┤
                   ├─ eligibility ─────▶ retrieve_documents → execute_tools
                   ├─ multi_step ──────▶ retrieve_documents → execute_tools
                   └─ clarification / refused ───────────────────────────┐
                                                                         ▼
            resolve_sources_and_rules ─▶ generate_answer ─▶ validate_and_audit ─▶ JSON
                   (CODE)                   (LLM)              (CODE)
```

In plain language: the question is sorted by plain code; the rulebooks and/or the student's record are
looked up; code keeps only the rules that apply on the as-of date and decides which document wins; the
AI model writes a short explanation from the verified facts; code double-checks it, attaches citations and
writes the audit record. A bounded model call can propose tool names before execution;
code validates that proposal and supplies identity and parameters. The model also writes prose.

| Node | File | Owns |
|---|---|---|
| classify_query | `app/graph/nodes/classify.py` | query_type, course resolution, header-only identity, refusals, clarifications |
| retrieve_documents | `nodes/retrieve.py` | top-k chunks from ChromaDB |
| execute_tools | `nodes/tools.py` | validated bounded tool proposal, SQLite tools + eligibility checks; `facts`, `assumptions`, the one-line `calculated_answer` |
| resolve_sources_and_rules | `nodes/resolve.py` → `app/rules/precedence.py` | Annex A, relative to `as_of_date` |
| generate_answer | `nodes/generate.py` | LLM explanation; NOT_FOUND handling; conflict message |
| validate_and_audit | `nodes/validate.py` | citation integrity, foreign-id scrubbing, upcoming-change note, audit row |

Retrieval fetches four times the configured top-k semantic candidates, then combines
cosine similarity with BM25 term matching before choosing the answer context. This helps
short clauses such as exceptional attendance relaxation survive the selection. The
semantic distance gate, programme scope, dates and authority checks still apply.
Resolved conflicts remain in the audit; only the winning clause reaches the model.
Missing eligibility rules and insufficient subject coverage return `not_found`.

Clarification follow-ups use an optional prior trace. The API checks the same account
header and policy date before continuing the pending question from its stored audit.
Short topic/course replies fill missing details; a fresh question replaces the pending
request. Topic/course buttons use the same path. Audits retain the original message,
completed question and prior trace, and the usual foreign-student guard still applies.

## 2. Where each answer type is decided

| answer_type | Decided by | Trigger |
|---|---|---|
| retrieved_fact | generate_answer | applicable evidence exists, LLM answered with `[S#]` labels |
| calculated | execute_tools (answer line) + generate_answer (explanation) | a tool/rule produced a verified result |
| not_found | resolve (no applicable evidence) **or** LLM replied `NOT_FOUND` | two independent safeguards |
| clarification_needed | classify_query | eligibility with no topic; personal attendance/result with no course |
| refused | classify_query | another student's id in the text; personal question with no header |
| conflict_flagged | resolve → generate | two docs, same authority level, same effective_from, different stated values |

## 3. Decisions and why

**Why RAG?** Policy lives in documents that change by circular. Grounding in retrieved text with citations
is the only way to be correct when judges ingest a document we have never seen (R1, R2, R11).

**Why SQLite + Python tools for student data?** Attendance %, marks and backlogs are exact values; a query plus
arithmetic is deterministic and auditable. An LLM reading a table is neither (R5).

**Why one LangGraph with fixed routing, and no agents?** Question types need different steps, and the routing
must be visible and testable. The workflow has six bounded nodes. Its optional tool proposal
is validated against allowed/required operations; it cannot supply a student identity or run arbitrary code.
Invalid plans use the fixed workflow and the plan/fallback is audited.

**Why keyword classification instead of asking the LLM?** The route decides whether personal data is touched
and whether to refuse. That must be reproducible for the evaluation and for R7. The domain vocabulary is
small; course names are resolved against the `courses` table, not guessed.

**Why metadata precedence in code (Annex A)?** Similarity cannot tell that the 2021 regulation expired, that
the 2026 circular supersedes clause 7.2, or that an FAQ saying "75 %" is outranked. So: similarity picks the
relevant chunks; metadata (dates, scope, supersedes, authority) decides which are applicable and which wins.
Clause-level supersession works because the chunker splits numbered clauses and records `clause` per chunk.

**Why is evidence selected by relevance and then ordered by authority?** Early on we ranked purely by
authority and the superseding circular fell out of the top-5 behind unrelated regulation clauses. Precedence
is for disagreement, not for relevance.

**Why deterministic eligibility with a rule registry?** "Am I eligible?" is `value OP threshold`. Thresholds
live in `rule_registry` rows that point at a cited clause; a circular that changes a threshold is a new row
with its own `effective_from`. Source dates, scope, supersession, authority and recency select
the applicable rule. Equal-priority differing thresholds abstain. Explicit minimum-attendance
amendments are registered on ingestion; other rule types require reviewed rows. The LLM is handed the verdict.

**Why does code write the one-line calculated answer?** With a 7–8B local model, the sentence a judge grades
("You are eligible…", "82.0 %") must not depend on the model. The model writes the friendlier explanation; if
it fails, the explanation is the list of facts.

**Why Ollama first, cloud only as fallback, mock last?** Guide §5. The chain means a dead model never breaks
the demo, and the audit record's `model` field shows which provider answered.

**Why documents are data.** Retrieved text sits in an `EVIDENCE:` block declared as quoted data; nothing in
the pipeline executes model output; level-5 documents never override; foreign student ids are scrubbed from
prose. Demo 7 shows a document that says "ignore previous instructions" having no effect (R8).

**Why header-only identity (R7)?** `classify_query` reads `student_id` only from the header. Any other id in
the text → `refused`. A personal question with no header → `refused`. Tools are never called with an id
from the text.

**Why MiniLM?** It embeds the small English corpus on CPU while GPU memory serves Ollama.
`EMBEDDING_PROVIDER=bge` offers another supported model; this setup has not benchmarked that comparison.

**Why Streamlit?** One-day build; the UI is scored for usability only and all logic is behind the API.

## 4. Live-judging risks and mitigations

| Risk | Mitigation |
|---|---|
| Ollama slow/dead | provider chain → cloud (if enabled) → mock; `LLM_TIMEOUT_S`; `model` in audit |
| Model download at demo time | embedding model baked into the Docker image; `ingest_documents.py` run beforehand; Chroma persisted |
| Judge ingests a PDF with no metadata | level 5, in force, cited only when nothing official answers |
| Judge ingests a circular superseding a clause | `DOC#clause` supersession at level 1/2; tests cover it |
| Two same-level same-date documents | `conflict_flagged`, both cited, "contact the issuing office" |
| Prompt-injection document | data-only prompt framing, level-5 rule, nothing executes model output |
| Judges' students S9xxx / JDG courses | loader validates then upserts; course resolution reads the table |
| `langgraph` version drift | `run_query_without_langgraph()` runs the identical routing in plain Python (used by tests) |
