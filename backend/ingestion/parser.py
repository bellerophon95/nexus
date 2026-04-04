import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.observability.tracing import observe

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    text: str
    tables: list[str]
    metadata: dict[str, Any]
    source_path: str


def _check_text_quality(text: str) -> bool:
    """
    Heuristic to detect 'garbage' extraction from PDFs (usually CID encoding issues).
    Returns False if the text is predominantly CID markers or non-alphanumeric noise.
    """
    if not text or len(text) < 100:
        return True  # Too short to judge fairly, assume OK or handled by other logic

    import re

    # Count CID markers like (cid:1), (cid:123), etc.
    cid_pattern = re.compile(r"\(cid:\d+\)")
    cid_matches = cid_pattern.findall(text)

    # If more than 10% of the 'words' appear to be CID markers, it's garbage
    if len(cid_matches) > (len(text) / 50):  # Heuristic threshold
        return False

    # Check for character variety (if it's almost all the same char, it's garbage)
    unique_chars = len(set(text[:2000]))
    return not (unique_chars < 5 and len(text) > 500)


def _fast_pdf_parser(
    file_path: str, progress_callback: Callable[[float], None] | None = None
) -> ParsedDocument | None:
    """
    Extracts text from PDF page by page using pypdf.
    Used for all PDFs — unstructured.io has been removed to save RAM.
    """
    from pypdf import PdfReader

    logger.info(f"Parsing PDF with pypdf: {file_path}")
    reader = PdfReader(file_path)
    num_pages = len(reader.pages)
    text_content = []

    for i, page in enumerate(reader.pages):
        text_content.append(page.extract_text() or "")
        if progress_callback:
            sub_progress = 5.0 + (10.0 * (i + 1) / num_pages)
            if num_pages < 50 or (i + 1) % 10 == 0 or (i + 1) == num_pages:
                progress_callback(sub_progress)

    full_text = "\n\n".join(text_content)

    if not _check_text_quality(full_text):
        logger.warning(
            f"Low-quality/garbage text detected in {file_path}. Text may be from a scanned/image PDF."
        )

    return ParsedDocument(
        text=full_text,
        tables=[],
        metadata={
            "filename": os.path.basename(file_path),
            "page_count": num_pages,
            "parser": "pypdf",
        },
        source_path=file_path,
    )


@observe()
def parse_document(
    file_path: str, progress_callback: Callable[[float], None] | None = None
) -> ParsedDocument:
    """
    Parses a document (PDF, DOCX, HTML, JSON) using pypdf or direct text reading.
    unstructured.io has been removed to reduce RAM usage on the production instance.
    Note: scanned/image PDFs will produce empty or low-quality text without OCR.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # 1. Direct read for plain text and data files
    if ext in [".txt", ".md", ".py", ".json", ".csv"]:
        logger.info(f"Directly reading text/data file: {file_path}")
        if progress_callback:
            progress_callback(7.0)
        with open(file_path, encoding="utf-8-sig", errors="ignore") as f:
            full_text = f.read()
        if progress_callback:
            progress_callback(15.0)
        return ParsedDocument(
            text=full_text,
            tables=[],
            metadata={"filename": os.path.basename(file_path)},
            source_path=file_path,
        )

    # 2. pypdf for all PDFs (replaces unstructured fallback)
    if ext == ".pdf":
        result = _fast_pdf_parser(file_path, progress_callback)
        if result:
            return result

    # 3. Fallback for unsupported types — attempt to read as plain text
    logger.warning(f"Unsupported file type '{ext}' — attempting plain text read.")
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
        return ParsedDocument(
            text=full_text,
            tables=[],
            metadata={"filename": os.path.basename(file_path)},
            source_path=file_path,
        )
    except Exception as e:
        raise ValueError(f"Cannot parse file {file_path}: {e}")
