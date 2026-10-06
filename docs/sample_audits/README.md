Four sample audit records from the active NSUT API and local Ollama, produced by
`scripts/make_sample_audits.py`. Student records are entirely fictional, and the November
conflict uses the two explicitly synthetic notices. Each file is the exact
payload `GET /audit/{trace_id}` returns, plus a `_response` block with the matching `/ask` fields.
Run `.venv/bin/python scripts/make_sample_audits.py` with the local API running to regenerate.
`--offline` instead uses the original non-NSUT regression fixtures and mock model.
