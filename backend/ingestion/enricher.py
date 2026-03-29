import spacy
import yake
from typing import List, Dict, Any, Tuple
import logging
from backend.observability.tracing import observe

logger = logging.getLogger(__name__)

# Lazy loading of resources
_nlp = None
_kw_extractor = None

def get_enricher_resources():
    global _nlp, _kw_extractor
    if _nlp is None:
        try:
            # We only need the NER component for efficiency if we want, 
            # but usually en_core_web_sm is fast enough.
            _nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {e}")
            raise
    if _kw_extractor is None:
        try:
            # YAKE parameters
            _kw_extractor = yake.KeywordExtractor(
                lan="en", 
                n=3,           # Max ngram size
                dedupLim=0.9,  # Deduplication threshold
                top=15,        # Number of keywords
                features=None
            )
        except Exception as e:
            logger.error(f"Failed to load YAKE extractor: {e}")
            raise
    return _nlp, _kw_extractor

@observe()
def enrich_chunk(text: str) -> Dict[str, Any]:
    """
    Enriches a single chunk with entities and topics/keywords.
    """
    nlp, kw_extractor = get_enricher_resources()
    
    # 1. Entity Extraction (NER)
    entities = []
    try:
        doc = nlp(text)
        entities = _extract_entities_from_doc(doc)
    except Exception as e:
        logger.error(f"NER extraction failed: {e}")

    # 2. Topic/Keyword Extraction
    topics = _extract_topics(text, kw_extractor)

    return {
        "entities": entities,
        "topics": topics,
        "key_phrases": topics[:5]
    }

def _extract_entities_from_doc(doc) -> List[Dict[str, str]]:
    entities = []
    seen_entities = set()
    for ent in doc.ents:
        ent_tuple = (ent.text.strip(), ent.label_)
        if ent_tuple not in seen_entities:
            entities.append({
                "text": ent_tuple[0],
                "label": ent_tuple[1]
            })
            seen_entities.add(ent_tuple)
    return entities

def _extract_topics(text: str, kw_extractor) -> List[str]:
    try:
        keywords_scores = kw_extractor.extract_keywords(text)
        return [kw for kw, score in keywords_scores]
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")
        return []

def enrich_chunks_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """
    Enriches a list of chunks efficiently using nlp.pipe.
    """
    nlp, kw_extractor = get_enricher_resources()
    results = []
    
    # Process NER in batch (nlp.pipe is much faster for many docs)
    # We disable unnecessary components for enrichment
    docs = nlp.pipe(texts, disable=["tagger", "parser", "attribute_ruler", "lemmatizer"], batch_size=16)
    
    for i, doc in enumerate(docs):
        entities = _extract_entities_from_doc(doc)
        topics = _extract_topics(texts[i], kw_extractor)
        
        results.append({
            "entities": entities,
            "topics": topics,
            "key_phrases": topics[:5]
        })
    
    return results
