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
    Extracts text from PDF page by page using pypdf for maximum speed on massive files.
    """
    from pypdf import PdfReader

    logger.info(f"Using Super Fast PDF extraction for {file_path}")
    reader = PdfReader(file_path)
    num_pages = len(reader.pages)
    text_content = []

    for i, page in enumerate(reader.pages):
        text_content.append(page.extract_text() or "")
        # Report progress within the 5% - 15% parsing range (total 10% range)
        if progress_callback:
            sub_progress = 5.0 + (10.0 * (i + 1) / num_pages)
            # Only report periodically for efficiency if it's a massive document
            if num_pages < 50 or (i + 1) % 10 == 0 or (i + 1) == num_pages:
                progress_callback(sub_progress)

    full_text = "\n\n".join(text_content)

    # Quality Check Fallback
    if not _check_text_quality(full_text):
        logger.warning(
            f"Detection of low-quality/garbage text (CID) in {file_path}. Falling back to unstructured."
        )
        return None

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
    Parses a document (PDF, DOCX, HTML, JSON) using unstructured.io or pypdf.
    Extracts text and tables separately.
    Handles plain text and massive PDFs directly to avoid expensive partitioning stalls.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    file_size = os.path.getsize(file_path)

    # 1. Bypass unstructured for plain text and data files
    if ext in [".txt", ".md", ".py", ".json", ".csv"]:
        logger.info(f"Directly reading text/data file: {file_path}")
        if progress_callback:
            progress_callback(7.0)  # Quick bump
        
        # Use utf-8-sig to handle Census/Excel CSVs with BOM markers, fallback to ignore errors
        with open(file_path, encoding="utf-8-sig", errors="ignore") as f:
            full_text = f.read()
            
        if progress_callback:
            progress_callback(15.0)  # Finished parsing
            
        return ParsedDocument(
            text=full_text,
            tables=[],
            metadata={"filename": os.path.basename(file_path)},
            source_path=file_path,
        )

    if ext == ".pdf" and file_size > 5 * 1024 * 1024:
        try:
            result = _fast_pdf_parser(file_path, progress_callback)
            if result:
                return result
            # If result is None, it means quality check failed, so we intentional fallback
        except Exception as e:
            logger.warning(f"Fast PDF extraction failed, falling back to unstructured: {e}")

    # 3. Standard path (unstructured.io) for complex/small files
    # LAZY IMPORT to save 512MB RAM on startup
    from unstructured.documents.elements import Table
    from unstructured.partition.auto import partition

    strategy = "fast" if file_size > 2 * 1024 * 1024 else "auto"
    logger.info(
        f"Partitioning {file_path} with strategy={strategy} (Size: {file_size / 1024 / 1024:.2f}MB)"
    )

    if progress_callback:
        progress_callback(6.0)  # Initial unstructured start

    elements = partition(filename=file_path, strategy=strategy)

    text_parts = []
    tables = []

    total_elements = len(elements)
    for i, element in enumerate(elements):
        if isinstance(element, Table):
            tables.append(element.text)
        else:
            text_parts.append(str(element))

        # Periodic update for unstructured as well, if we have many elements
        if progress_callback and (i % 50 == 0 or i == total_elements - 1):
            sub_progress = 6.0 + (9.0 * (i + 1) / (total_elements or 1))
            progress_callback(sub_progress)

    full_text = "\n\n".join(text_parts)

    metadata = {}
    if elements:
        metadata = elements[0].metadata.to_dict()

    return ParsedDocument(text=full_text, tables=tables, metadata=metadata, source_path=file_path)
