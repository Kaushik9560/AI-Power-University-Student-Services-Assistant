<!-- OWNER: infra. TODO step 8: keep deployment and component diagrams current. -->

# Architecture

The API accepts a student question, passes an append-only state through retrieval, student-data tools, rule resolution, answer generation, and audit validation, then returns the stable `/ask` response shape.

Area modules own their implementation files. Shared graph, API, configuration, and dependency files require coordination before editing.
