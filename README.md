# AI-Powered University Student Services Assistant

This branch updates the shared scaffold to the latest local project structure and
publishes Kaushik's frontend, API, deterministic classifier and LangGraph integration
scope while retaining Butola006's already-merged RAG contribution. It is a partial team contribution, with AI assistance disclosed below.

The listed contribution files and the existing RAG modules contain implementation.
Remaining unimplemented Python modules contain a docstring placeholder; datasets contain column headers without records;
policy PDFs and model/runtime artifacts are not included. Teammates will add their
implementations from their own accounts.

## Included contribution

- Streamlit UI: `ui/streamlit_app.py`
- FastAPI flow: `app/main.py`, `app/api/routes.py`, `app/api/schemas.py`
- Clarification context: `app/services/conversation.py`
- Deterministic classification and access checks: `app/graph/nodes/classify.py`,
  `app/graph/nodes/_common.py`
- Shared graph state and routing: `app/graph/state.py`, `app/graph/workflow.py`,
  `app/graph/nodes/__init__.py`
- Conversation integration tests: `tests/test_conversation.py`
- Isolated API boundary regressions: `tests/test_api_flow.py`

## Integration status

The complete assistant will run after the pending backend modules and synthetic
fixtures are contributed and integrated. Current API and graph imports require the
pending bootstrap, database, audit, tools, rules and generation modules.
RAG upload/source endpoints remain available; unanswered student-service requests
return HTTP 503 until their backend modules are integrated.
Conversation tests also require the pending test fixtures. A passing run of the full
private codebase does not imply this partial branch passes those integration tests.

Student identity comes from the `X-Student-Id` header. Personal queries require an
identity; queries naming another student are refused. Conversation follow-ups are
bound to the same account and policy date. The classifier uses deterministic routing.

See `PROJECT_STRUCTURE.md` for all target paths and
`docs/team_contribution.md` for implementation scope. Source code remains in its
existing team history; these commits record the current integration changes.
