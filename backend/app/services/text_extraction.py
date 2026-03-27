from pathlib import Path

import docx2txt
import pypdf


def extract_text_from_file(path: str, *, content_type: str | None = None) -> str:
    p = Path(path)
    suffix = p.suffix.lower()

    if content_type == "application/pdf" or suffix == ".pdf":
        reader = pypdf.PdfReader(str(p))
        texts: list[str] = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts).strip()

    if (
        content_type
        in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        or suffix == ".docx"
    ):
        return (docx2txt.process(str(p)) or "").strip()

    # fallback: treat as UTF-8 text
    return p.read_text(encoding="utf-8", errors="ignore").strip()

