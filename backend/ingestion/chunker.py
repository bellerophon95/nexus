import spacy
from sentence_transformers import SentenceTransformer
import numpy as np
import tiktoken
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import logging
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

@dataclass
class Chunk:
    text: str
    index: int
    token_count: int
    metadata: Dict[str, Any]

# Lazy loading of models to avoid overhead on import
_tokenizer = None

def _hard_split_text(text: str, max_chars: int) -> List[str]:
    """
    Fallback splitter for segments that are too long for semantic processing.
    """
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

def get_resources():
    global _nlp, _model, _tokenizer
    if _nlp is None:
        try:
            # Use a blank "en" model with a sentencizer for maximum speed/reliability
            _nlp = spacy.blank("en")
            _nlp.add_pipe("sentencizer")
            # Increase max_length to handle large segments (up to 10M chars)
            _nlp.max_length = 10000000 
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}")
            raise
    if _model is None:
        try:
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            raise
    if _tokenizer is None:
        try:
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"Failed to load tiktoken encoding: {e}")
            raise
    return _nlp, _model, _tokenizer

def count_tokens(text: str) -> int:
    _, _, tokenizer = get_resources()
    return len(tokenizer.encode(text))

@observe()
def semantic_chunking(
    text: str, 
    metadata: Dict[str, Any], 
    threshold_percentile: float = 95,
    max_tokens: int = 512,
    min_tokens: int = 50,
    progress_callback: Optional[Callable[[float], None]] = None,
    start_progress: float = 20.0,
    end_progress: float = 40.0
) -> List[Chunk]:
    """
    Performs semantic chunking with High-Performance optimizations for large docs.
    """
    nlp, model, tokenizer = get_resources()
    
    # Heuristic: Use ultra-fast sentencizer for massive documents (>1M chars)
    is_massive = len(text) > 1000000
    if is_massive:
        logger.info(f"Massive document detected ({len(text)} chars). Enabling High-Performance Mode.")
    
    # 1. Segment massive text into manageable blocks
    SEGMENT_SIZE = 500000 if not is_massive else 1000000
    text_segments = [text[i:i + SEGMENT_SIZE] for i in range(0, len(text), SEGMENT_SIZE)]
    total_segments = len(text_segments)
    
    logger.info(f"Processing {total_segments} segments (Mode: {'High-Performance' if is_massive else 'Standard'})")
    
    all_sentences = []
    
    # 2. Extract sentences using nlp.pipe for efficiency
    # Progress: 20% -> 30% for sentence extraction
    extraction_start = start_progress
    extraction_end = start_progress + (end_progress - start_progress) * 0.3
    
    logger.info("Extracting sentences...")
    docs = nlp.pipe(text_segments, batch_size=8)
    
    for i, doc in enumerate(docs):
        for sent in doc.sents:
            s_text = sent.text.strip()
            if not s_text:
                continue
            
            # Safety Valve: If sentencizer fails (due to no punctuation/garbage), 
            # don't allow a single "sentence" to be huge.
            if len(s_text) > 4000:
                logger.warning(f"Extremely long sentence detected ({len(s_text)} chars). Forcing hard-split.")
                all_sentences.extend(_hard_split_text(s_text, 2000))
            else:
                all_sentences.append(s_text)
        
        if progress_callback:
            p = extraction_start + (i + 1) / total_segments * (extraction_end - extraction_start)
            progress_callback(min(p, extraction_end))

    if not all_sentences:
        return []

    # 3. Batch Embed sentences (much faster than per-segment)
    # Progress: 30% -> 40% for batch embedding
    embedding_start = extraction_end
    embedding_end = end_progress
    
    logger.info(f"Batch embedding {len(all_sentences)} sentences...")
    if progress_callback:
        progress_callback(embedding_start)
        
    embeddings = model.encode(all_sentences, batch_size=64, show_progress_bar=False)
    
    if progress_callback:
        progress_callback(embedding_end)

    # 4. Semantic Splitting based on embeddings
    logger.info("Calculating semantic boundaries...")
    distances = []
    for i in range(len(embeddings) - 1):
        norm_a = np.linalg.norm(embeddings[i])
        norm_b = np.linalg.norm(embeddings[i+1])
        sim = np.dot(embeddings[i], embeddings[i+1]) / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
        distances.append(1 - sim)

    # Identify breakpoints
    breakpoint_threshold = np.percentile(distances, threshold_percentile) if distances else 0.5
    breakpoints = [i for i, x in enumerate(distances) if x > breakpoint_threshold]
    
    all_chunks = []
    current_global_idx = 0
    start_sent_idx = 0
    
    for breakpoint_idx in breakpoints:
        chunk_text = " ".join(all_sentences[start_sent_idx : breakpoint_idx + 1])
        all_chunks.append(Chunk(
            text=chunk_text,
            index=current_global_idx,
            token_count=len(tokenizer.encode(chunk_text)),
            metadata=metadata.copy()
        ))
        start_sent_idx = breakpoint_idx + 1
        current_global_idx += 1
        
    # Final block
    if start_sent_idx < len(all_sentences):
        chunk_text = " ".join(all_sentences[start_sent_idx:])
        all_chunks.append(Chunk(
            text=chunk_text,
            index=current_global_idx,
            token_count=len(tokenizer.encode(chunk_text)),
            metadata=metadata.copy()
        ))
    
    logger.info(f"Completed semantic chunking: {len(all_chunks)} chunks generated.")
    return all_chunks
