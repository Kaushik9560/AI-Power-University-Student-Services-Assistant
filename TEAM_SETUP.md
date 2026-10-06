# Team integration setup

Use Python 3.12. This branch contains Kaushik's integration scope and placeholders
for the remaining team modules. Fill or merge those modules before launching the
complete app or running its end-to-end tests.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
```

The integrated app additionally needs Ollama with `llama3.1:8b`, the registered public
policies, synthetic CSV fixtures and, for scanned PDFs, Tesseract and Poppler.
Do not commit `.env`, installed environments/models, databases, logs or real student
records. Use synthetic student information only.
