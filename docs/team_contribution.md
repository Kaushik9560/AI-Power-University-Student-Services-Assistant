# Team contribution statement (fill in before submission — guide §9.4)

| Member | Owned area (branch) | Files | Can explain |
|---|---|---|---|
| _name_ | rag | `app/rag/*`, `app/graph/nodes/retrieve.py`, `data/documents/*`, `scripts/ingest_documents.py` | chunking, embeddings choice, live ingest |
| _name_ | student-data | `app/db/*`, `app/tools/*`, `app/graph/nodes/tools.py`, `data/synthetic/*`, `scripts/generate_students.py`, `scripts/validate_students.py`, `scripts/load_students.py` | schema, tools, synthetic data kit |
| _name_ | rules | `app/rules/*`, `app/graph/nodes/resolve.py`, `tests/test_precedence.py`, `tests/test_eligibility.py` | Annex A precedence, rule registry, eligibility |
| _name_ | llm + ui + audit-eval | `app/services/llm.py`, `app/graph/prompts.py`, `app/graph/nodes/generate.py`, `app/graph/nodes/validate.py`, `app/audit/*`, `ui/*`, `scripts/evaluation.py` | prompt design, fallback chain, evaluation method |

Git history: every member commits on their own branch and squash-merges to `main` (see `CONTRIBUTING.md`).
