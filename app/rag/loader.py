"""Load Markdown, text, and PDF sources with normalized register metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass(frozen=True)
class DocumentMetadata:
    doc_id: str
    title: str
    issuer: str = "Unknown"
    authority_level: int = 5
    doc_type: str = "other"
    version: str = "1.0"
    effective_from: str | None = None
    effective_to: str | None = None
    supersedes: tuple[str, ...] = ()
    scope_programmes: tuple[str, ...] = ()
    scope_batches: str = "ALL"
    provenance: str = ""
    retrieved_on: str = ""
    synthetic: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "issuer": self.issuer,
            "authority_level": self.authority_level,
            "doc_type": self.doc_type,
            "version": self.version,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "supersedes": list(self.supersedes),
            "scope_programmes": list(self.scope_programmes),
            "scope_batches": self.scope_batches,
            "provenance": self.provenance,
            "retrieved_on": self.retrieved_on,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class LoadedDocument:
    metadata: DocumentMetadata
    pages: list[tuple[int | None, str]]

    @property
    def text(self) -> str:
        return "\n\n".join(text for _, text in self.pages)


def _list_value(value: Any) -> tuple[str, ...]:
    if value is None or str(value).strip().upper() == "ALL":
        return ()
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r"[;,]", str(value))
    return tuple(str(item).strip() for item in items if str(item).strip())


def _date_value(value: Any) -> str | None:
    if value in (None, "", "nan"):
        return None
    if hasattr(value, "date"):
        value = value.date()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return date.fromisoformat(str(value).strip()).isoformat()


def build_metadata(raw: dict[str, Any], fallback_title: str) -> DocumentMetadata:
    doc_type = str(raw.get("doc_type") or "other").strip().lower()
    authority = raw.get("authority_level")
    if authority in (None, ""):
        authority = {"regulation": 1, "ordinance": 1, "circular": 2, "notification": 2,
                     "notice": 3, "handbook": 4, "faq": 4}.get(doc_type, 5)
    authority = int(authority)
    if authority not in range(1, 6):
        raise ValueError("authority_level must be between 1 and 5")

    title = str(raw.get("title") or fallback_title).strip()
    doc_id = str(raw.get("doc_id") or re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper())
    effective_from = _date_value(raw.get("effective_from"))
    effective_to = _date_value(raw.get("effective_to"))
    if effective_from and effective_to and effective_to < effective_from:
        raise ValueError("effective_to cannot be earlier than effective_from")
    batches = raw.get("scope_batches") or "ALL"
    if isinstance(batches, (list, tuple)):
        batches = ";".join(str(value) for value in batches)
    synthetic = raw.get("synthetic", True)
    if not isinstance(synthetic, bool):
        synthetic = str(synthetic).strip().lower() in {"y", "yes", "true", "1"}

    return DocumentMetadata(
        doc_id=doc_id,
        title=title,
        issuer=str(raw.get("issuer") or "Unknown").strip(),
        authority_level=authority,
        doc_type=doc_type,
        version=str(raw.get("version") or "1.0").strip(),
        effective_from=effective_from,
        effective_to=effective_to,
        supersedes=_list_value(raw.get("supersedes")),
        scope_programmes=_list_value(raw.get("scope_programmes")),
        scope_batches=str(batches).strip() or "ALL",
        provenance=str(raw.get("provenance") or "").strip(),
        retrieved_on=_date_value(raw.get("retrieved_on")) or date.today().isoformat(),
        synthetic=synthetic,
    )


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\t", " ")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_markdown(content: str, fallback_title: str, override: dict[str, Any] | None = None) -> LoadedDocument:
    metadata: dict[str, Any] = {}
    match = _FRONT_MATTER.match(content)
    if match:
        try:
            parsed = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            parsed = {}
            for line in match.group(1).splitlines():
                key, separator, value = line.partition(":")
                if separator:
                    parsed[key.strip()] = value.strip().strip("'\"")
        if parsed is not None and not isinstance(parsed, dict):
            raise ValueError("front matter must contain a YAML mapping")
        metadata = parsed or {}
        content = content[match.end():]
    if override:
        metadata.update({key: value for key, value in override.items() if value not in (None, "")})
    return LoadedDocument(build_metadata(metadata, fallback_title), [(None, clean_text(content))])


def parse_pdf(path: Path, metadata: dict[str, Any] | None = None) -> LoadedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF ingestion requires pypdf; install project requirements") from exc

    pages = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = clean_text(page.extract_text() or "")
        if len(text) < 40 and get_settings().ocr_enabled:
            try:
                from pdf2image import convert_from_path
                import pytesseract

                images = convert_from_path(str(path), first_page=page_number, last_page=page_number, dpi=200)
                text = clean_text(pytesseract.image_to_string(images[0])) if images else text
            except Exception:  # noqa: BLE001
                pass
        if text:
            pages.append((page_number, text))
    return LoadedDocument(build_metadata(metadata or {}, path.stem), pages)


def load_file(path: Path, metadata: dict[str, Any] | None = None) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path, metadata)
    if suffix in {".md", ".markdown", ".txt"}:
        return parse_markdown(path.read_text(encoding="utf-8", errors="replace"), path.stem, metadata)
    raise ValueError(f"Unsupported document type: {suffix}; expected .md, .txt, or .pdf")


def load_bytes(filename: str, content: bytes, metadata: dict[str, Any] | None = None) -> LoadedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return parse_markdown(content.decode("utf-8", errors="replace"), Path(filename).stem, metadata)
    if suffix == ".pdf":
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            return parse_pdf(Path(temp_file.name), metadata)
    raise ValueError(f"Unsupported document type: {suffix}; expected .md, .txt, or .pdf")