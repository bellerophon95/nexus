# NEXUS — Development Milestones

> Incremental release plan for Project NEXUS. Each milestone is a shippable, testable increment that meaningfully advances the system.

## Release Overview

| Milestone | Name | Outcome |
|---|---|---|
| [M1](./M1-foundation.md) | Foundation & Infrastructure | Deployable skeleton, all infra provisioned |
| [M2](./M2-ingestion.md) | Document Ingestion Pipeline | Documents can be parsed, chunked, and indexed |
| [M3](./M3-retrieval.md) | Hybrid Retrieval Pipeline | Semantic + keyword search with reranking live |
| [M4](./M4-basic-rag.md) | Basic RAG + Query API | End-to-end Q&A working via API |
| [M5](./M5-agents.md) | Multi-Agent Orchestration | LangGraph agents handling complex multi-hop queries |
| [M6](./M6-guardrails.md) | Guardrails & Safety | Input/output safety, PII protection, hallucination blocking |
| [M7](./M7-observability.md) | Observability & Evals | Full tracing, RAGAS metrics, CI regression gate |
| [M8](./M8-frontend.md) | Frontend + Semantic Cache | Chat UI live, semantic caching reducing latency & cost |
| [M9](./M9-cicd-launch.md) | CI/CD & Production Launch | Automated deploys, smoke tests, production-ready |

## Execution Philosophy

- **Each milestone = a release.** Ship something real at every stage.
- **No orphaned work.** Every piece of code is connected to a working system before the next begins.
- **Tests travel with features.** Unit tests are written alongside the code they cover.
- **Infra is provisioned once** in M1 and reused — no re-provisioning surprises mid-build.
