# Teammate setup

Extract the ZIP and open the `university-ai-assistant` folder. Use Python 3.12 and
install Ollama on your machine. The ZIP contains source, required policy documents,
fictional student data, tests and documentation.

On Ubuntu, install the scanned-PDF tools:

```bash
sudo apt install tesseract-ocr tesseract-ocr-eng poppler-utils
```

Create the Python environment and local configuration:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
```

Start Ollama in a separate terminal if it is not already running:

```bash
ollama serve
```

Download the model, then start the project from its root:

```bash
ollama pull llama3.1:8b
.venv/bin/python scripts/run_local.py
```

Open http://localhost:8501; API documentation is at http://localhost:8000/docs.
First startup loads the synthetic CSVs and indexes the registered PDFs. Later starts
reuse the local index. The embedding model downloads on first use. The launcher also
recognizes a demo that is already running.

Use demo student S1001 and ask “Am I eligible for the end-semester exam in DBMS?”
All student records are fictional. The fee notice applies to the 2022–23 admission
cohort, although its user-provided library title is FEE_2026.

```bash
.venv/bin/python -m pytest tests -q
```

See `docs/local_setup.md` for the project-local runtime alternative and
`docs/demo_script.md` for the demo sequence. Configure your own `.env`; installed
models/environments, generated databases, secrets and logs are not part of the ZIP.
