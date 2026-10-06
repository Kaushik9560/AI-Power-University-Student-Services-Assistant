# Local development setup

Use Python 3.12, matching the Docker image. The local installation lives in `.venv/`;
downloaded runtimes, models and logs are ignored by Git. No cloud API key is needed.

## Install dependencies

From the repository root, using `uv`:

```bash
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
uv venv --python 3.12 .venv
# The small embedding model runs on CPU; Ollama uses the NVIDIA GPU for the LLM.
uv pip install --python .venv/bin/python torch --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/bin/python -r requirements.txt
```

For the exact versions used in this setup, install `requirements.lock` instead:

```bash
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match -r requirements.lock
```

Copy `.env.example` to `.env` if `.env` does not already exist. Keep local configuration
and any credentials in that ignored file.

## Ollama and models

The current workspace uses Ollama 0.35.1 extracted into `.local/ollama/`, with
`llama3.1:8b` stored under `.local/ollama/models/`. The official manual installation
instructions are at [Ollama Linux setup](https://docs.ollama.com/linux).
To install the same runtime into a fresh Linux x86-64 checkout:

```bash
mkdir -p .local/ollama .runtime
curl -fL --retry 3 -o .runtime/ollama-linux-amd64.tar.zst \
  https://github.com/ollama/ollama/releases/download/v0.35.1/ollama-linux-amd64.tar.zst
tar --zstd -xf .runtime/ollama-linux-amd64.tar.zst -C .local/ollama
OLLAMA_MODELS="$PWD/.local/ollama/models" OLLAMA_CONTEXT_LENGTH=4096 \
  OLLAMA_NUM_PARALLEL=1 OLLAMA_NO_CLOUD=1 .local/ollama/bin/ollama serve
```

In another terminal, download the configured model:

```bash
.local/ollama/bin/ollama pull llama3.1:8b
```

The GPU driver must work first (`nvidia-smi`). The launcher bounds context to 4096
tokens, enables Flash Attention with a q8_0 KV cache, and serves one generation at a
time for the RTX 3050's 6 GB VRAM. These are supported
[Ollama memory settings](https://docs.ollama.com/faq).
Check actual GPU offload with `.local/ollama/bin/ollama ps` after asking a question.

## Load data and start

```bash
.venv/bin/python scripts/load_students.py
HF_HOME="$PWD/.hf" ANONYMIZED_TELEMETRY=false \
.venv/bin/python scripts/ingest_documents.py
.venv/bin/python scripts/run_local.py
```

The student loader validates CSVs and upserts them in one transaction. Use `--replace`
only when you intentionally want to replace the supplied tables. Document ingestion
replaces chunks by document ID; run it when documents or chunk settings change.

The active `.env` follows `.env.example`: the public NSUT PDFs in
`data/nsut/source_register.csv`, three verified rules in `data/nsut/rule_registry.csv`,
and fictional records in `data/nsut/synthetic/`. The active database is `data/nsut.db`;
the original demo database and policy fixtures are preserved separately.

Startup loads missing baseline data and indexes missing documents only; existing Chroma
chunks are reused. The launcher makes `.env` override stale terminal exports, starts
Ollama when the configured local server is absent,
then waits for the API and UI to respond. It binds both to localhost:

- UI: <http://localhost:8501>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

Logs are in `.runtime/api.log`, `.runtime/ui.log`, and `.runtime/ollama.log`.
Ctrl+C stops services started by the launcher; an Ollama server that was already running
is reused and left running. For a launcher started in the background, send SIGTERM:

```bash
kill "$(cat .runtime/launcher.pid)"
```

Use `.venv/bin/python -m pytest tests -q` for offline regression tests.
Run the real-model evaluation after the model has downloaded:

```bash
HF_HOME="$PWD/.hf" ANONYMIZED_TELEMETRY=false \
  .venv/bin/python scripts/evaluation.py --questions data/evaluation/nsut_questions.jsonl \
  --compare --out docs/nsut_evaluation_report.md
```

## Before submission

The active NSUT source register contains three real public policy PDFs and two clearly
marked future synthetic notices used for conflict/date checks, plus a fictional level-4
handbook for authority-based conflict resolution on 2026-10-07. All student data remains synthetic. The original synthetic policy
fixtures are retained for regression tests and are excluded from the NSUT collection.
See `data/nsut/README.md` for provenance, document-date limitations and unsupported
placement thresholds. Team member names in `docs/team_contribution.md` still need
filling in. Re-run evaluation after changing documents.

Git metadata is unavailable in this mounted workspace, so the branch and remote cannot
be verified here. No commit, push, merge or publication was performed during setup.
Docker files are provided, but no Docker engine is installed here; runtime verification
is pending. See `docs/requirements_review.md` for the guide checklist and remaining limits.
