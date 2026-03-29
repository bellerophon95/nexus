import sys
import os
sys.path.append(os.getcwd())

from backend.retrieval.reranker import rerank_results

def test_reranker():
    query = "How does the Nexus ingestion pipeline work?"
    chunks = [
        {
            "id": "1",
            "document_id": "doc1",
            "text": "The Nexus ingestion pipeline handles document processing and chunking.",
            "similarity": 0.8
        },
        {
            "id": "2",
            "document_id": "doc2",
            "text": "Solar panels are green energy sources.",
            "similarity": 0.7
        }
    ]
    
    print(f"Reranking {len(chunks)} chunks for query: '{query}'")
    reranked = rerank_results(query, chunks, top_k=5)
    
    print(f"\nReranked results:")
    for i, r in enumerate(reranked):
        print(f"{i+1}. [Score: {r.get('rerank_score', 'N/A'):.4f}] {r['text']}")

if __name__ == "__main__":
    test_reranker()
