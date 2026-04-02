import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.observability.tracing import observe

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    text: str
    index: int
    token_count: int
    metadata: dict[str, Any]


# Lazy loading of models to avoid overhead on import
_nlp = None
_model = None
_tokenizer = None


def _hard_split_text(text: str, max_chars: int) -> list[str]:
    """
    Fallback splitter for segments that are too long for semantic processing.
    """
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def get_resources():
    global _nlp, _model, _tokenizer
    if _nlp is None:
        try:
            import spacy

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
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            raise
    if _tokenizer is None:
        try:
            import tiktoken

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
    metadata: dict[str, Any],
    threshold_percentile: float = 95,
    max_tokens: int = 512,
    min_tokens: int = 50,
    progress_callback: Callable[[float], None] | None = None,
    start_progress: float = 20.0,
    end_progress: float = 40.0,
) -> list[Chunk]:
    """
    Performs semantic chunking with High-Performance optimizations for large docs.
    """
    nlp, model, tokenizer = get_resources()

    # Heuristic: Use ultra-fast sentencizer for massive documents (>1M chars)
    is_massive = len(text) > 1000000
    if is_massive:
        logger.info(
            f"Massive document detected ({len(text)} chars). Enabling High-Performance Mode."
        )

    # 1. Segment massive text into manageable blocks
    # 2,000,000 chars (~2MB) is the sweet spot for keeping RAM < 1GB
    SEGMENT_SIZE = 1000000 if not is_massive else 2000000
    text_segments = [text[i : i + SEGMENT_SIZE] for i in range(0, len(text), SEGMENT_SIZE)]
    total_segments = len(text_segments)

    logger.info(
        f"Processing {total_segments} segments (Mode: {'High-Performance' if is_massive else 'Standard'})"
    )

    all_chunks = []
    current_global_idx = 0

    for seg_idx, segment in enumerate(text_segments):
        logger.info(f"Chunking segment {seg_idx + 1}/{total_segments}...")
        
        # 2. Extract sentences for THIS segment
        doc = nlp(segment)
        seg_sentences = []
        for sent in doc.sents:
            s_text = sent.text.strip()
            if not s_text:
                continue
            if len(s_text) > 4000:
                seg_sentences.extend(_hard_split_text(s_text, 2000))
            else:
                seg_sentences.append(s_text)
        
        if not seg_sentences:
            continue

        # 3. Embed sentences for THIS segment
        # This prevents the embedding matrix from growing to the size of the whole doc
        embeddings = model.encode(seg_sentences, batch_size=64, show_progress_bar=False)

        # 4. Semantic Splitting for THIS segment
        distances = []
        for i in range(len(embeddings) - 1):
            norm_a = np.linalg.norm(embeddings[i])
            norm_b = np.linalg.norm(embeddings[i + 1])
            sim = (
                np.dot(embeddings[i], embeddings[i + 1]) / (norm_a * norm_b)
                if norm_a > 0 and norm_b > 0
                else 0.0
            )
            distances.append(1 - sim)

        # Identify breakpoints
        breakpoint_threshold = np.percentile(distances, threshold_percentile) if distances else 0.5
        breakpoints = [i for i, x in enumerate(distances) if x > breakpoint_threshold]

        start_sent_idx = 0
        for b_idx in breakpoints:
            chunk_text = " ".join(seg_sentences[start_sent_idx : b_idx + 1])
            all_chunks.append(
                Chunk(
                    text=chunk_text,
                    index=current_global_idx,
                    token_count=len(tokenizer.encode(chunk_text)),
                    metadata=metadata.copy(),
                )
            )
            start_sent_idx = b_idx + 1
            current_global_idx += 1

        # Final block for this segment
        if start_sent_idx < len(seg_sentences):
            chunk_text = " ".join(seg_sentences[start_sent_idx:])
            all_chunks.append(
                Chunk(
                    text=chunk_text,
                    index=current_global_idx,
                    token_count=len(tokenizer.encode(chunk_text)),
                    metadata=metadata.copy(),
                )
            )
            current_global_idx += 1

        if progress_callback:
            p = start_progress + (seg_idx + 1) / total_segments * (end_progress - start_progress)
            progress_callback(min(p, end_progress))

    logger.info(f"Completed segmented semantic chunking: {len(all_chunks)} chunks generated.")
    return all_chunks
