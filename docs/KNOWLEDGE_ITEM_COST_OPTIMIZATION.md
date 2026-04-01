# Knowledge Item: Nexus Cost-Optimized Architecture

## Context
Project Nexus was originally designed as a high-compute RAG system using local NLI models (DeBERTa) for Self-RAG. During the March 2026 alignment phase, we pivoted to an **LLM-based Validation** approach to maintain a **$5/month** budget.

## Core Principles
1.  **Zero RAM Tax:** Avoid loading heavy ML models (NLI, Classifiers) on the FastAPI backend. This keeps the instance size small (512MB–1GB).
2.  **LLM-as-Validator:** Use `gpt-4o-mini` for:
    *   **Query Routing** (was DeBERTa classifier).
    *   **Hallucination Detection** (was DeBERTa-v3-small NLI).
3.  **Managed Free Tiers:** 
    *   **Supabase:** Primary metadata and sparse search.
    *   **Qdrant Cloud:** Dense retrieval (managed free tier vs. self-hosting to save RAM).
    *   **Upstash Redis:** Semantic caching.

## Trade-offs (Rationale)
*   **Privacy:** Some context data leaves the VPC for OpenAI APIs.
*   **Latency:** Slightly higher per-check latency but zero cold-start time (no 1.5GB model to load).
*   **Observability:** LLMs provide structured JSON explanations for failures, whereas local NLI just provides a score.

## Current State
*   `README.md` and `docs/NEXUS_README.md` have been updated with `[ACTIVE]` and `[PHASED]` labels to reflect this roadmap.
