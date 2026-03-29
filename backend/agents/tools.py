from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from backend.retrieval.searcher import search_knowledge_base
import logging

logger = logging.getLogger(__name__)

@tool
def vector_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search the Project Nexus knowledge base for relevant document chunks.
    Use this tool to find factual information, technical details, or context 
    needed to answer a user's question.
    """
    try:
        logger.info(f"Executing vector search for query: {query}")
        # Use our existing hybrid search + reranking pipeline
        results = search_knowledge_base(
            query=query,
            limit=limit,
            rerank=True,
            match_threshold=0.2
        )
        
        # Format results for the agent
        formatted_results = []
        for res in results:
            formatted_results.append({
                "text": res.get("text", ""),
                "metadata": res.get("metadata", {}),
                "score": res.get("rerank_score") or res.get("similarity", 0.0)
            })
            
        return formatted_results
    except Exception as e:
        logger.error(f"Vector search tool failed: {e}")
        return [{"error": str(e)}]

@tool
def web_search_stub(query: str) -> str:
    """
    Search the web for up-to-date information not found in the local knowledge base.
    [STUB] Currently returns a placeholder as external search is not yet configured.
    """
    return "Web search is currently unavailable. Please rely on the local knowledge base."

# Export tools
NEXUS_TOOLS = [vector_search, web_search_stub]
