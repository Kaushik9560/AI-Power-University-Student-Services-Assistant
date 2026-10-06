# AI-Powered University Student Services Assistant

A modular student-services assistant built around retrieval, student records, university rules, auditable decisions, and a simple web interface.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run the test suite with `pytest tests -q`.

## Working in parallel

| Branch | Owned files | Steps |
|---|---|---|
| `rag` | `app/rag/*`, retrieval node, source documents, ingestion script | 1, 5 |
| `student-data` | database, tools, tools node, synthetic data, loader, tool tests | 2 |
| `rules` | rules, resolution node, eligibility and precedence tests | 3, 4, 5 |
| `llm` | LLM service, prompts, generation node | 1, 4 |
| `audit-eval` | audit, validation node, evaluation script and data | 6 |
| `ui` | `ui/*` | 7 |
| `infra` | container files, README and docs | 8 |

Shared files are `app/graph/state.py`, `app/graph/workflow.py`, `app/graph/nodes/_common.py`, `app/api/schemas.py`, `app/api/routes.py`, `app/config.py`, `.env.example`, and `requirements.txt`. Coordinate before editing them and keep shared changes in a separate commit.

Use commit messages in the form `area: what changed`. Never commit `.env`, `data/chroma/`, or local database files.

## Area contracts

- The tools node writes `tool_results.facts`, `tools_used`, and `student`.
- The rules node writes `applicable_rules`, `rule_outcomes`, and `verdict`.
- Student tools are plain functions and raise `ToolError` on failure.
- Evaluation consumes only the response returned by `POST /ask`.
