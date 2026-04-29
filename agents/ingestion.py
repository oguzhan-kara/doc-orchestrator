import io
from pathlib import Path
import pdfplumber


def ingest_file(content: bytes, filename: str) -> str:
    """Parse uploaded file bytes into plain text."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(content)
    return content.decode("utf-8", errors="replace").strip()


def ingest_text(raw: str) -> str:
    """Normalize inline text input."""
    return raw.strip()


def _extract_pdf(content: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts).strip()
