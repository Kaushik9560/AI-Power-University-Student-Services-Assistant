# University Student Services Assistant

An AI assistant for NSUT policy questions, attendance and exam eligibility.
Uses public university documents and fictional student records.

## Features

- Policy answers with source citations
- Attendance and eligibility checks using deterministic tools
- Document uploads, conflict resolution and audit traces

**Stack:** Streamlit · FastAPI · LangGraph · ChromaDB · SQLite · Ollama

## Run locally

Requires **Python 3.12** and **Ollama running locally**.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
test -f .env || cp .env.example .env
ollama pull llama3.1:8b
python scripts/run_local.py
```

Open **http://localhost:8501**. First startup loads the demo data and policy index.

## Try it

Select student **S1001** and ask:

> Am I eligible for the end-semester exam in DBMS?

[Detailed setup](docs/local_setup.md) · [Architecture](docs/architecture.md) · [Demo prompts PDF](docs/demo_testing_prompts.pdf)
