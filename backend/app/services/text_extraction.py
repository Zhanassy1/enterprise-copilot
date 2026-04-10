from dataclasses import dataclass
from pathlib import Path

import docx2txt
import pypdf


@dataclass
class ExtractedDocument:
    text: str
    page_count: int | None
    language: str | None


def detect_language(text: str) -> str | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    cyr = sum(1 for ch in cleaned if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    lat = sum(1 for ch in cleaned if "a" <= ch.lower() <= "z")
    if cyr == 0 and lat == 0:
        return None
    if cyr > lat * 1.3:
        return "ru"
    if lat > cyr * 1.3:
        return "en"
    return "mixed"


def extract_text_metadata_from_file(path: str, *, content_type: str | None = None) -> ExtractedDocument:
    p = Path(path)
    suffix = p.suffix.lower()

    if content_type == "application/pdf" or suffix == ".pdf":
        reader = pypdf.PdfReader(str(p))
        texts: list[str] = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        merged = "\n\f\n".join(texts).strip()
        return ExtractedDocument(text=merged, page_count=len(reader.pages), language=detect_language(merged))

    if (
        content_type
        in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        or suffix == ".docx"
    ):
        text = (docx2txt.process(str(p)) or "").strip()
        return ExtractedDocument(text=text, page_count=None, language=detect_language(text))

    # fallback: treat as UTF-8 text
    text = p.read_text(encoding="utf-8", errors="ignore").strip()
    return ExtractedDocument(text=text, page_count=None, language=detect_language(text))


def extract_text_from_file(path: str, *, content_type: str | None = None) -> str:
    return extract_text_metadata_from_file(path, content_type=content_type).text

