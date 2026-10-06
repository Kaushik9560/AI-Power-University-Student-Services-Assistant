# Working in parallel

| Area (branch) | Files you own |
|---|---|
| `rag` | `app/rag/*`, `app/graph/nodes/retrieve.py`, `data/documents/*`, `data/source_register.csv`, `scripts/ingest_documents.py` |
| `student-data` | `app/db/*`, `app/tools/*`, `app/graph/nodes/tools.py`, `data/synthetic/*`, `scripts/generate_students.py`, `scripts/validate_students.py`, `scripts/load_students.py`, `tests/test_tools.py` |
| `rules` | `app/rules/*`, `app/graph/nodes/resolve.py`, `tests/test_precedence.py`, `tests/test_eligibility.py` |
| `llm` | `app/services/llm.py`, `app/graph/prompts.py`, `app/graph/nodes/generate.py` |
| `audit-eval` | `app/audit/*`, `app/graph/nodes/validate.py`, `scripts/evaluation.py`, `scripts/make_sample_audits.py`, `data/evaluation/*`, `docs/evaluation_report.md` |
| `ui` | `ui/*` |
| `infra` | `Dockerfile`, `docker-compose.yml`, `README.md`, `docs/*` |

Shared files — say so in chat before editing, keep the change tiny, separate commit:
`app/graph/state.py` (append keys only), `app/graph/workflow.py`, `app/graph/nodes/_common.py`,
`app/api/schemas.py`, `app/api/routes.py`, `app/config.py`, `.env.example`, `requirements.txt`.

```bash
git checkout main && git pull
git checkout -b rules                 # your area
# small commits, each leaves the app runnable; commit at least hourly (guide §5.1)
pytest tests -q                       # must pass before pushing
git push -u origin rules              # PR → review by one teammate → squash-merge
```

Rules: `main` always starts and passes tests; one PR = one area; never commit `.env`, `data/chroma/`,
`data/*.db`; messages `area: what changed`. Tag the final commit `final`.

Interfaces between areas: `tools.py` writes `facts`, `assumptions`, `tools_invoked`, `applied_rules`, `verdict`,
`calculated_answer`; `resolve.py` writes `evidence`, `dropped_sources`, `upcoming_changes`, `conflicts`,
`precedence_decision`; `generate.py` reads all of them; `validate.py` writes `citations` and the audit row.
