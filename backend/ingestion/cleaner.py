import unicodedata
import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import hashlib
from backend.database.supabase import supabase
from backend.observability.tracing import observe

@dataclass
class CleanedDocument:
    text: str
    fingerprint: int
    is_duplicate: bool
    metadata: Dict[str, Any]

def normalize_text(text: str) -> str:
    """
    Normalizes text (NFKC), collapses whitespace, and removes boilerplate.
    """
    # Unicode decomposition/composition
    text = unicodedata.normalize("NFKC", text)
    
    # Whitespace collapse (multiple spaces -> one space)
    text = re.sub(r'[\s\t]+', ' ', text)
    
    # Strip leading/trailing whitespace
    return text.strip()

def check_duplicate(fingerprint: int) -> bool:
    """
    Checks if a document with a similar fingerprint already exists in Supabase.
    """
    try:
        response = supabase.table("documents").select("id").eq("fingerprint", fingerprint).execute()
        return len(response.data) > 0
    except Exception:
        return False

@observe()
def clean_document(text: str, metadata: Dict[str, Any]) -> CleanedDocument:
    """
    Cleans the parsed text and generates a stable SHA-256 fingerprint.
    Checks for duplicates in the database.
    """
    cleaned_text = normalize_text(text)
    
    # Generate 64-bit fingerprint from SHA-256
    sha256_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()
    # Take first 16 chars (64 bits) and convert to signed 64-bit int
    unsigned_fp = int(sha256_hash[:16], 16)
    fingerprint = (unsigned_fp + 2**63) % 2**64 - 2**63
    
    # Check for duplicates
    is_duplicate = check_duplicate(fingerprint)
    
    return CleanedDocument(
        text=cleaned_text,
        fingerprint=fingerprint,
        is_duplicate=is_duplicate,
        metadata=metadata
    )
