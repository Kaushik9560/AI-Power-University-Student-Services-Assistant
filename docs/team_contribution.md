# Team contribution scope

| Scope | Contributor | Status |
|---|---|---|
| Streamlit frontend, FastAPI request/response flow, clarification context | Kaushik (`Kaushik9560`) | Implemented in this branch, AI-assisted |
| Deterministic classifier and access checks | Kaushik (`Kaushik9560`) | Implemented in this branch, AI-assisted |
| LangGraph shared state, conditional edges and orchestration | Kaushik (`Kaushik9560`) | Implemented in this branch, AI-assisted |
| Conversation integration tests and isolated API boundary tests | Kaushik (`Kaushik9560`) | Included; require remaining backend and fixtures |
| RAG loading/chunking/embeddings/store, retrieval node, configuration and RAG tests | Butola006 | Existing main contribution preserved, with original history |
| Database/tools, rules, LLM/generation, audit, bootstrap, fixtures and remaining scripts/tests | Owning teammates | Placeholders; contributors will add their implementations |

Exact implementation files are listed in the root README. Configuration and dataset
headers describe the integration contract; they contain no teammate backend code or
student records. Existing commits and teammate branches are preserved. API compatibility adjustments
keep the existing RAG ingestion contract while integrating the new request flow.
