# Team integration

This branch contains Kaushik's frontend/API, classifier and graph-orchestration
contribution. Other implementation files are placeholders so each member can add
their own code from their own account.

Fetch the `kaushik` branch before starting integration. Create an area branch from
that layout, fill only your owned modules, then open a pull request for team review.
Existing member branches remain available; merge their actual implementations with
care because some earlier interfaces differ from this layout.

API integration requires bootstrap/data loading, audit storage, retrieval ingestion,
embeddings/store health functions, student tools, graph-node exports, rules and LLM
generation. `tests/test_conversation.py` additionally needs synthetic fixtures and a
working audit/pipeline implementation. The complete backend must pass integration
tests before this partial contribution is promoted to `main`.

Use `git add -p` for shared tracked files. For an untracked file, use `git add -N`
first if you need to stage only selected hunks. Never commit `.env`, models, local
environments, databases, logs or real student information. Disclose AI assistance
and credit the actual contributor for each implementation.
