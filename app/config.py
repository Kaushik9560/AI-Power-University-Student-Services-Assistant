"""
Central configuration. Every tunable is read from the environment (see .env.example).
Nothing else in the app calls os.getenv.

LLM policy (hackathon guide §5): Ollama is the primary model. A cloud model may be used
ONLY as a fallback behind CLOUD_FALLBACK=true (disclosed in README). MOCK_LLM=true runs
the whole pipeline with a deterministic stand-in for tests and evaluation.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = PROJECT_ROOT / "data"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _flag(name: str, default: str = "false") -> bool:
    return _env(name, default).lower() in ("1", "true", "yes", "y")


def _path(name: str, default: Path) -> Path:
    path = Path(_env(name, str(default))).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


class Settings:
    # ---- LLM (primary = Ollama) ------------------------------------------
    MOCK_LLM: bool = _flag("MOCK_LLM")
    LLM_PROVIDER: str = _env("LLM_PROVIDER", "ollama")          # ollama | mock
    OLLAMA_BASE_URL: str = _env("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = _env("OLLAMA_MODEL", "llama3.1:8b")
    LLM_TIMEOUT_S: float = float(_env("LLM_TIMEOUT_S", "60"))
    # Cloud fallback (optional, disclosed). Used only if Ollama fails.
    CLOUD_FALLBACK: bool = _flag("CLOUD_FALLBACK")
    CLOUD_PROVIDER: str = _env("CLOUD_PROVIDER", "openai")      # openai-compatible | anthropic
    CLOUD_BASE_URL: str = _env("CLOUD_BASE_URL", "https://api.openai.com/v1")
    CLOUD_API_KEY: str = _env("CLOUD_API_KEY")
    CLOUD_MODEL: str = _env("CLOUD_MODEL", "gpt-4o-mini")
    # Last-resort fallback so the demo never shows a stack trace.
    MOCK_FALLBACK: bool = _flag("MOCK_FALLBACK", "true")

    # ---- Embeddings / vector store ----------------------------------------
    EMBEDDING_PROVIDER: str = _env("EMBEDDING_PROVIDER", "minilm")   # minilm | bge | hash(tests)
    EMBEDDING_MODEL: str = _env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    CHROMA_DIR: Path = _path("CHROMA_DIR", DATA_DIR / "chroma" / "nsut")
    CHROMA_COLLECTION: str = _env("CHROMA_COLLECTION", "university_docs")

    # ---- Retrieval ----------------------------------------------------------
    RETRIEVAL_TOP_K: int = int(_env("RETRIEVAL_TOP_K", "8"))
    EVIDENCE_MAX_CHUNKS: int = int(_env("EVIDENCE_MAX_CHUNKS", "5"))
    RETRIEVAL_MAX_DISTANCE: float = float(_env("RETRIEVAL_MAX_DISTANCE", "0.75"))
    CHUNK_SIZE_CHARS: int = int(_env("CHUNK_SIZE_CHARS", "900"))
    CHUNK_OVERLAP_CHARS: int = int(_env("CHUNK_OVERLAP_CHARS", "150"))
    OCR_ENABLED: bool = _flag("OCR_ENABLED")   # needs pytesseract + pdf2image + tesseract binary

    # ---- Databases / paths ----------------------------------------------------
    SQLITE_PATH: Path = _path("SQLITE_PATH", DATA_DIR / "nsut.db")
    AUDIT_DB_PATH: Path = _path("AUDIT_DB_PATH", DATA_DIR / "nsut-audit.db")
    DOCUMENTS_DIR: Path = _path("DOCUMENTS_DIR", DATA_DIR / "nsut" / "documents")
    SOURCE_REGISTER: Path = _path("SOURCE_REGISTER", DATA_DIR / "nsut" / "source_register.csv")
    SYNTHETIC_DIR: Path = _path("SYNTHETIC_DIR", DATA_DIR / "nsut" / "synthetic")
    RULE_REGISTRY_PATH: Path = _path("RULE_REGISTRY_PATH", SYNTHETIC_DIR / "rule_registry.csv")
    TOOL_PLANNING: bool = _flag("TOOL_PLANNING", "true")

    # ---- API / UI -------------------------------------------------------------
    API_HOST: str = _env("API_HOST", "0.0.0.0")
    API_PORT: int = int(_env("API_PORT", "8000"))
    API_BASE_URL: str = _env("API_BASE_URL", "http://localhost:8000")
    DEFAULT_STUDENT_ID: str = _env("DEFAULT_STUDENT_ID", "S1001")


settings = Settings()
