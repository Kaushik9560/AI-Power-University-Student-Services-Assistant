"""
Document loading and Source Register metadata (guide Annex B).

Metadata fields: doc_id, title, issuer, authority_level (1-5, Annex A), doc_type, version,
effective_from, effective_to, supersedes ("DOC" or "DOC#clause", ';'-separated),
scope_programmes ("ALL" or list), scope_batches ("ALL", list, or "2023+"),
provenance, retrieved_on, synthetic (Y/N).

The same fields come from source_register.csv, from a Markdown front-matter block, or
from the metadata JSON on POST /ingest. Document *content* is always treated as data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

AUTHORITY_LEVELS = {
    1: "Statutes, ordinances, academic regulations",
    2: "Official circulars and notifications from an authorised office",
    3: "Department notices",
    4: "Handbooks and FAQs",
    5: "Unofficial content (untrusted; informational only)",
}
DOC_TYPE_TO_AUTHORITY = {
    "regulation": 1, "ordinance": 1, "statute": 1, "act": 1,
    "circular": 2, "notification": 2,
    "notice": 3, "department_notice": 3,
    "handbook": 4, "faq": 4,
    "unofficial": 5, "other": 5,
}


@dataclass
class DocumentMetadata:
    doc_id: str
    title: str
    issuer: str = "Unknown"
    authority_level: int = 5
    doc_type: str = "other"
    version: str = "1.0"
    effective_from: str | None = None
    effective_to: str | None = None
    supersedes: list[str] = field(default_factory=list)      # ["ACAD-REG-2021", "ACAD-REG-2024#7.2"]
    scope_programmes: list[str] = field(default_factory=list)  # [] == ALL
    scope_batches: str = "ALL"                                 # "ALL" | "2023+" | "2023;2024"
    provenance: str = ""
    retrieved_on: str = field(default_factory=lambda: date.today().isoformat())
    synthetic: bool = True

    # ---- serialisation --------------------------------------------------
    def to_register_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["supersedes"] = ";".join(self.supersedes)
        d["scope_programmes"] = ";".join(self.scope_programmes) if self.scope_programmes else "ALL"
        d["effective_from"] = self.effective_from or ""
        d["effective_to"] = self.effective_to or ""
        d["synthetic"] = "Y" if self.synthetic else "N"
        return d

    def to_chroma(self) -> dict[str, Any]:
        """Chroma metadata must be scalar."""
        row = self.to_register_row()
        row["authority_level"] = int(self.authority_level)
        return row

    @staticmethod
    def from_row(d: dict[str, Any]) -> "DocumentMetadata":
        return build_metadata(d, fallback_title=str(d.get("title") or d.get("doc_id") or "Untitled"))


@dataclass
class LoadedDocument:
    metadata: DocumentMetadata
    pages: list[tuple[int | None, str]]   # (page_number or None, text)

    @property
    def text(self) -> str:
        return "\n\n".join(t for _, t in self.pages)


# --------------------------------------------------------------------------
# metadata normalisation
# --------------------------------------------------------------------------
def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s or s.upper() == "ALL":
        return []
    return [x.strip() for x in re.split(r"[;,]", s) if x.strip()]


def _as_date(v) -> str | None:
    if v in (None, "", "nan"):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    return date.fromisoformat(s).isoformat() if s else None


def _as_bool(v, default=True) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().upper() in ("Y", "YES", "TRUE", "1")


def build_metadata(raw: dict[str, Any], fallback_title: str = "Untitled") -> DocumentMetadata:
    doc_type = str(raw.get("doc_type") or "other").strip().lower()
    authority = raw.get("authority_level")
    if authority in (None, ""):
        authority = DOC_TYPE_TO_AUTHORITY.get(doc_type, 5)
    authority = int(authority)
    if not 1 <= authority <= 5:
        raise ValueError("authority_level must be between 1 and 5")

    title = str(raw.get("title") or fallback_title).strip()
    doc_id = str(raw.get("doc_id") or re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper()[:40]).strip()

    batches = raw.get("scope_batches")
    if isinstance(batches, (list, tuple)):
        batches = ";".join(str(b) for b in batches)
    batches = (str(batches).strip() if batches not in (None, "") else "ALL")

    result = DocumentMetadata(
        doc_id=doc_id,
        title=title,
        issuer=str(raw.get("issuer") or "Unknown").strip(),
        authority_level=authority,
        doc_type=doc_type,
        version=str(raw.get("version") or "1.0").strip(),
        effective_from=_as_date(raw.get("effective_from")),
        effective_to=_as_date(raw.get("effective_to")),
        supersedes=_as_list(raw.get("supersedes")),
        scope_programmes=_as_list(raw.get("scope_programmes")),
        scope_batches=batches if batches else "ALL",
        provenance=str(raw.get("provenance") or "").strip(),
        retrieved_on=_as_date(raw.get("retrieved_on")) or date.today().isoformat(),
        synthetic=_as_bool(raw.get("synthetic"), default=True),
    )
    if result.effective_from and result.effective_to and result.effective_from > result.effective_to:
        raise ValueError("effective_to cannot be earlier than effective_from")
    return result


# --------------------------------------------------------------------------
# scope helpers (used by precedence.py and eligibility.py)
# --------------------------------------------------------------------------
def programme_in_scope(programme: str | None, scope: list[str]) -> bool:
    """Empty scope == ALL. Matching is case-insensitive and tolerant of 'B.Tech' vs 'BTech'."""
    if not scope or not programme:
        return True

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    p = norm(programme)
    return any(norm(s) == p or norm(s) == "all" or (len(norm(s)) >= 4 and p.startswith(norm(s))) for s in scope)


def batch_in_scope(batch_year: int | str | None, scope: str | None) -> bool:
    """scope: 'ALL' | '2023+' | '2023;2024' | '2023,2024' | '2021-2023'."""
    if not scope or str(scope).strip().upper() == "ALL" or batch_year in (None, ""):
        return True
    try:
        year = int(batch_year)
    except ValueError:
        return True
    s = str(scope).strip()
    if s.endswith("+"):
        return year >= int(s[:-1])
    m = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", s)
    if m:
        return int(m.group(1)) <= year <= int(m.group(2))
    years = {int(x) for x in re.findall(r"\d{4}", s)}
    return year in years if years else True


# --------------------------------------------------------------------------
# file loading
# --------------------------------------------------------------------------
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\t", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_markdown(content: str, fallback_title: str, override: dict | None = None) -> LoadedDocument:
    m = _FRONT_MATTER.match(content)
    raw: dict = {}
    body = content
    if m:
        try:
            raw = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            # Hand-written metadata often has unquoted colons; fall back to simple key: value lines.
            raw = {}
            for line in m.group(1).splitlines():
                k, sep, v = line.partition(":")
                if sep:
                    raw[k.strip()] = v.strip().strip("'\"")
        body = content[m.end():]
    if override:
        raw.update({k: v for k, v in override.items() if v not in (None, "")})
    return LoadedDocument(metadata=build_metadata(raw, fallback_title), pages=[(None, clean_text(body))])


def _ocr_page(pdf_path: Path, page_index: int) -> str:
    """Optional OCR for scanned pages. Requires pytesseract + pdf2image + tesseract binary."""
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(str(pdf_path), first_page=page_index + 1, last_page=page_index + 1, dpi=200)
        return pytesseract.image_to_string(images[0]) if images else ""
    except Exception:  # noqa: BLE001 — OCR is best-effort
        return ""


def parse_pdf(pdf_path: Path, metadata: dict | None, fallback_title: str) -> LoadedDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int | None, str]] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if len(text.strip()) < 40 and settings.OCR_ENABLED:
            text = _ocr_page(pdf_path, i)
        text = clean_text(text)
        if text:
            pages.append((i + 1, text))
    raw = dict(metadata or {})
    sidecar = pdf_path.with_suffix(".yaml")
    if not raw and sidecar.exists():
        raw = yaml.safe_load(sidecar.read_text()) or {}
    return LoadedDocument(metadata=build_metadata(raw, fallback_title), pages=pages)


def load_file(path: Path, metadata: dict | None = None) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        return parse_markdown(path.read_text(encoding="utf-8", errors="ignore"), path.stem, override=metadata)
    if suffix == ".pdf":
        return parse_pdf(path, metadata, path.stem)
    raise ValueError(f"Unsupported document type: {path.suffix} (use .md, .txt or .pdf)")


def load_bytes(filename: str, data: bytes, metadata: dict | None) -> LoadedDocument:
    """Used by POST /ingest. Writes PDFs to a temp file because pypdf needs a path for OCR."""
    suffix = Path(filename).suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        return parse_markdown(data.decode("utf-8", errors="ignore"), Path(filename).stem, override=metadata)
    if suffix == ".pdf":
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return parse_pdf(tmp_path, metadata, Path(filename).stem)
        finally:
            tmp_path.unlink(missing_ok=True)
    raise ValueError(f"Unsupported document type: {suffix} (use .md, .txt or .pdf)")
